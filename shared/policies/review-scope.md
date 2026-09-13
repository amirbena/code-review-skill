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

## Semantic change-implication reasoning

The sections below each own one recurring failure mode in depth, but nothing
so far directs a reviewer, for an arbitrary change, to first ask *which
system-level dimensions this change materially implicates* at all. This
section is that base pass: for each dimension the change's own evidence
actually implicates, it performs the minimum bounded reasoning itself — it
is not solely a router to the deeper sections below. Those sections, and
any domain-specific deepening capability layered on top of the base
review, may add further depth to a dimension this pass already activates
when materially warranted; none of them may gate, weaken, narrow, or
replace this base obligation. Base semantic reasoning is unconditional
with respect to additional domain-specific depth — a deeper capability may
build on an implicated dimension, but it never determines whether that
dimension is considered at all. How a deeper capability is selected,
activated, or composed with the base review is outside this section's
scope.

### Canonical dimensions

The taxonomy below is a routing and reasoning aid, **not** a
mutually-exclusive classification — one change, or one piece of evidence
within it, may materially implicate several dimensions at once. A dimension
with no material activation signal in the change is not analysed and
produces no output, including no `not-applicable` record; this is
deliberately not an eight-dimension checklist run on every diff.

- **User-facing / client behavior** — signal: the change alters what a
  human end user sees, can do, or is told (rendered content, interaction
  state, client-side validation, accessibility-relevant markup, an
  error/success message a user reads). Base reasoning: does the new or
  changed behavior remain correct and safe across the states a real user can
  reach (loading, error, empty, partial, repeated interaction), and does any
  user-controlled or externally-sourced value reach rendered output or a
  client-visible decision without the handling that context requires. Depth
  owner: no dedicated owner contract exists yet in this repository; this
  base obligation is currently the full extent of review for this
  dimension.
- **Concurrency / distributed-system semantics** — signal: shared mutable
  state read and later acted on, more than one process or thread able to
  observe or mutate the same state, or a message/event that can be
  delivered more than once or out of order. Base reasoning: could two
  concurrent executions interleave in a way that violates an invariant the
  code assumes holds. Depth owner: "Architectural placement and
  execution-lifecycle fidelity" (concurrency or ordering-guarantee trigger)
  and "Failure state, retry safety, and recovery" below.
- **Data / persistence** — signal: a schema, migration, stored
  representation, or the durable shape of data written or read by the
  change. Base reasoning: does the change preserve read/write compatibility
  with existing stored data and existing readers/writers of it. Depth
  owner: "Existing behavior ownership" below, and "Findings beyond the
  changed lines" in [`evidence.md`](evidence.md) for readers/writers outside
  the diff.
- **API / integration contracts** — signal: a request/response shape, an
  event/message schema, a function or interface signature, or any other
  boundary another component already depends on. Base reasoning: does the
  change preserve the contract's meaning for existing callers/consumers, or
  is the break intentional and actually propagated to them. Depth owner:
  "API / contract compatibility review" below for schema/contract backward
  compatibility, "Affected-test / test-impact analysis" below, and
  "Architectural placement and execution-lifecycle fidelity"'s
  caller/callee-contract trigger.
- **Infrastructure / deployment** — signal: the change alters how or where
  code runs, is built, or is deployed (build/deploy configuration,
  container/orchestration definitions, environment- or platform-specific
  behavior, a startup/shutdown sequence). Base reasoning: does the change
  behave correctly across the environments and deployment states it can
  actually run in, and does it fail safely if a dependency it now assumes
  is unavailable. Depth owner: no dedicated owner contract exists yet in
  this repository; this base obligation is currently the full extent of
  review for this dimension.
- **Security / trust boundaries** — signal: a value crosses from a less
  trusted context into a more trusted one, or the change touches
  authentication, authorization, or a policy-enforcement decision. Base
  reasoning: is the boundary still enforced at the point that actually
  matters, for every path that can reach it. Depth owner: "Architectural
  placement and execution-lifecycle fidelity"'s authorization/
  permission-enforcement trigger.
- **Operability / production-readiness** — signal: the change introduces or
  materially changes a failure mode that a production operator would need
  to detect or diagnose. Base reasoning: would this failure mode be visible
  through the repository's own established observability mechanism, or
  otherwise effectively undiagnosable. Depth owner: "Failure state, retry
  safety, and recovery" below, "Observability is applicability-gated, not
  universal."
- **Performance / scale** — signal: the change alters an algorithmic
  complexity, a per-request or per-item cost, or a resource (memory,
  connection, file handle, thread) that is acquired but not obviously
  bounded or released. Base reasoning: does the change remain correct and
  bounded at the volume the surrounding code is actually exercised with, not
  merely at the scale exercised by its own tests. Depth owner:
  "Change-risk signals and review depth" below and
  [`repository-expansion.md`](repository-expansion.md) for how far dependent
  call sites are followed.

### Worked example — one change implicating several dimensions

A change that adds a new webhook endpoint which persists the received
payload and re-renders a summary of it in an admin dashboard implicates
**API / integration contracts** (the webhook's request shape is now a
contract with its sender), **data / persistence** (the payload is now
stored, so schema and idempotent-write behavior matter),
**security / trust boundaries** (the payload originates outside the trust
boundary and later reaches rendered output), and **user-facing / client
behavior** (what the admin dashboard actually displays). It does not
implicate concurrency, infrastructure, or performance/scale unless the
change's own evidence separately supports one of those signals — reasoning
about the four implicated dimensions above is not extended to the other
four merely because the taxonomy lists them.

### Evidence is semantic, not structural

File type, framework, path, and language are evidence that a dimension
*may* be implicated — never solely authoritative on their own, and never a
substitute for the semantic signal itself. The same structural shape can
implicate a dimension in one change and not another; reason from what the
change actually does, not from its extension or directory. Four
language-neutral worked examples, one per representative evidence shape:

- **Shared-state read→decide→write**: a counter, balance, or availability
  value is read, compared against a threshold, and then written back,
  regardless of language or storage technology — implicates concurrency
  whenever more than one caller can reach the same state.
- **User-controlled value reaching rendered output**: any value that
  originates from a request, upload, or external message and is later
  included in content shown to a user or another system — implicates
  security/trust boundaries and user-facing behavior regardless of the
  templating or rendering technology involved.
- **Schema or persisted-state change**: a change to a stored record's shape,
  meaning, or default — implicates data/persistence regardless of whether
  the storage is a relational schema, a document shape, a cache entry, or a
  serialized file format.
- **Deployment or configuration change**: a change to how, where, or under
  what settings code runs — implicates infrastructure/deployment regardless
  of whether it is expressed as a container manifest, a CI workflow, an
  environment-variable default, or an application configuration file.

### Bounded expansion and stop conditions

Once a dimension is activated, investigate it using the same
minimum-context-first, one-ring-at-a-time model and stop conditions already
defined under "Architectural placement and execution-lifecycle fidelity" —
including that **"insufficient evidence" is a valid terminal outcome** for
a dimension, not a reason to speculate about it or to keep expanding
indefinitely. This section introduces no second scope or evidence model:
blast radius, the confirmed-defect / credible-engineering-risk /
optional-improvement evidence labeling, and the no-repository-wide-audit
boundary in [`evidence.md`](evidence.md) govern here exactly as they do
everywhere else in this policy.

## Null-like absence-risk review

Inspect changed data-flow and control-flow for credible **null-like
absence** risk — null-pointer dereference, `undefined` / `null` property
or method access, `nil` dereference, `None` attribute/index access, an
unchecked optional-lookup result, or a nullable return value assumed
present — whenever the reviewed language admits that failure mode at all.
This is a **semantic rule keyed to the reviewed language's nullability
model, never a regex or keyword match**: it applies identically whether
the language is Java/Kotlin, JavaScript/TypeScript, C#, Python, Go, or any
other language with equivalent null/nil/undefined semantics, and it reads
what a value's absence would actually do at the point of use, not whether
a variable is named `value` or a method is named `get`. A credible risk is
raised only when the diff's own evidence supports it; purely theoretical
nullability — a value that could in principle be null somewhere in the
type system but is demonstrably safe at every reachable use the diff
introduces — is not reported. This section adds no new finding category:
a surfaced risk is classified under [`severity.md`](severity.md) and
evidenced per [`evidence.md`](evidence.md) exactly like any other finding,
and carries no dedicated severity merely because a nullable value is
present.

### Credible absence paths

Representative patterns — illustrative, not an exhaustive keyword list, and
not something to flag merely because the shape superficially appears:

- dereference, member/method access, invocation, indexing, or
  destructuring of a value before a null/undefined/nil/None check that the
  surrounding code elsewhere treats as necessary;
- an optional or lookup result (map/dictionary `get`, `find`, a query-one
  call, a configuration or environment lookup) used without handling the
  absent case;
- a nullable return value from a changed function assumed present by a
  caller, or a changed caller that drops a present absence-check on a
  callee's nullable return;
- JavaScript/TypeScript property or method access, indexing, or
  destructuring on a value that can be `null` or `undefined` at that point;
- a nullable collection element or map value used as though always
  present;
- a `nil` / `None` value passed into code that assumes a concrete,
  non-absent object.

### Interoperability and escape-hatch boundaries

Platform and language boundaries that weaken a language's normal
null-safety guarantees deserve the same scrutiny as ordinary flow, because
the type system can no longer be trusted to rule absence out: a Kotlin
platform type originating from Java interop, TypeScript `any`, an `as`
cast, or a non-null assertion (`!`) that overrides the compiler's own
nullability tracking, C#'s null-forgiving `!` operator or
nullable-oblivious legacy code, `unsafe`/cgo/reflection code that steps
outside normal compile-time guarantees, and deserialization of external
data into a typed shape the type system treats as non-null but the source
payload does not guarantee. At these boundaries, reason about what is
actually guaranteed by the runtime or the data source, not what the
declared type alone claims.

### Suppression

Do not report a finding when a guard, early return, assertion, the
language's own type-system guarantee (a genuinely non-nullable type, not
merely the absence of a visible check), a framework or contract guarantee,
or demonstrable upstream validation already makes the value safe at the
point of use. The review question is always whether *this* code path can
actually reach the access with an absent value, not whether the value's
declared type permits absence in the abstract — noisy blanket "this could
be null" findings with no reachable failure path are exactly what this
section does not want. A language that encodes nullability strongly in its
type system (for example, a non-nullable-by-default type system) shifts
review effort toward the escape hatches and interoperability boundaries
above rather than ordinary flow already covered by the compiler.

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

## API / contract compatibility review

Signal: the change modifies a repository contract another component
consumes across a boundary that need not be visible as a call site in the
diff — an OpenAPI or JSON Schema document, a protobuf/IDL definition, a
public API request/response model or DTO, an event/message schema, or a
configuration contract read by another service or job. Recognizing the
contract type is a diff-level signal (a schema/IDL file changed, a public
model's field set or type changed, a documented event/message shape
changed); it is never itself the finding.

Base reasoning: classify each changed contract element as **compatible**,
**breaking**, or **context-dependent** by its change shape, reasoned from
existing consumers' actual expectations, never a hypothetical worst case:

- **Additive, optional** (a new optional field/property, a new endpoint or
  message type) — compatible: no existing consumer's expectations change.
- **Field or property removed** — breaking: an existing consumer that
  reads it loses the value outright.
- **Optional narrowed to required** — breaking: it invalidates inputs an
  existing consumer already sends without the new requirement.
- **Property or field renamed** — breaking in both directions: existing
  readers of the old name stop finding it, and existing senders never
  learn the new one.
- **Enum member removed** — breaking: no existing consumer can already
  tolerate a value it has never seen ceasing to exist.
- **Enum member added** — **context-dependent**: additive for a consumer
  that ignores unknown members, breaking for one with an exhaustive
  switch/case or closed-set validation. The diff alone cannot establish
  which kind of consumer exists.
- **Incompatible type change** (a widened or narrowed representation, or
  changed semantics of an existing value) — breaking when it can produce a
  value an existing consumer's prior assumptions do not admit.

Fail-closed on unresolvable consumer intent: when the actual consumer
population, or its tolerance for an additive change like a new enum
member, cannot be established from the diff and any available context,
this pass does not invent a required breaking finding for it — inventing a
breakage claim the diff cannot support is worse than reporting nothing. It
may still surface the ambiguity as an optional, non-blocking note naming
the specific unresolved question, which never raises severity or forces
`CHANGES REQUIRED` on its own. This is the same fail-closed discipline
"Architectural placement and execution-lifecycle fidelity" and "Semantic
change-implication reasoning" above already apply to insufficient
evidence, not a new evidence standard invented for this section alone.

This section adds no new severity, finding category, or probability
score: a breaking-shape finding is labeled confirmed defect / credible
engineering risk per [`evidence.md`](evidence.md) like any other finding,
and classified per [`severity.md`](severity.md) — a consumer-facing
contract break is typically P1, scaled by the change's actual blast
radius per [`evidence.md`](evidence.md), "Findings beyond the changed
lines," when the real consumer surface is broader or narrower than the
change alone shows. The closed change-shape table above, the recognized
contract types and their diff-recognition detail, and the smallest useful
first implementation are the API/contract compatibility model design
record (a repository-development document, named here, not linked because
it is not a packaged resource).

This is not a second scope model, and it duplicates neither a schema
linter nor a SAST tool: it is one concrete depth owner, for schema/contract
backward compatibility specifically, of the "API / integration contracts"
dimension in "Semantic change-implication reasoning" above — alongside,
not replacing, "Affected-test / test-impact analysis" above (which traces
the change into dependent tests) and "Architectural placement and
execution-lifecycle fidelity"'s caller/callee-contract trigger (which
follows call sites actually present in the diff's blast radius). This
section instead reasons about consumers that need never appear as a call
site at all — an external API client, an event subscriber, or a
configuration reader outside the diff's own repository. It never fetches
or retrieves another repository's consumer code to resolve that ambiguity;
an unresolved consumer surface is exactly the fail-closed case above, not
a reason to expand retrieval.

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
