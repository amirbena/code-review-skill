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

## Candidate-finding validation

Every section below that ends in a finding — "Emit a finding only with
concrete evidence …" or the equivalent — presupposes that the candidate
reaching that point has already been validated, not merely observed. An
unusual code shape, a branch difference, or a structural inconsistency is
an **observation** first; promoting it to a **candidate claim** requires
naming the contract/invariant/expected-behavior it violates, showing the
causal chain from the reviewed change to a concrete, observable incorrect
result, and — for a claimed regression — the specific four-part regression
evidence set. When the candidate's own reasoning depends on comparing two
or more usages, paths, or implementations, it additionally requires
establishing that the compared usages serve the same semantic
responsibility before the comparison can support the claim — this
condition does not apply, and is not a prerequisite, for a candidate with
no such comparison (a standalone technical-invariant violation, for
example, needs no compared usage at all). Before a blocking candidate is accepted,
actively try to invalidate it against the available review context
(disconfirmation). None of this requires a tracker ticket: a
technically-grounded blocking finding (a race, a broken invariant, a
security-boundary bypass, a deterministic failure, a data-loss path) is
fully supported with no Jira reference at all. The full pipeline, its six
validation gates, the evidence/contract grounding hierarchy, and the
separation of a finding's validity from whether it independently clears
the P0/P1 blocking bar are owned by the candidate-finding validation model
(a repository-development document, not a packaged resource, so it is
named here, not linked) and are not restated here.

This is not a second scope, evidence, or severity model: the
confirmed-defect / credible-engineering-risk / optional-improvement
labeling in [`evidence.md`](evidence.md) and the P0/P1/P2 definitions and
mechanical decision derivation in [`severity.md`](severity.md) are
unchanged. This section only gates *what a candidate must prove* before it
reaches that labeling; blast-radius scoping for a candidate that clears it
reuses [`repository-expansion.md`](repository-expansion.md) and
[`architectural-placement.md`](architectural-placement.md) unchanged.

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
activated, or composed with the base review is owned by "Domain-specific
deepening pass" below, not by this section.

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
  and "Failure state, retry safety, and recovery" below, and, when the
  evidence gathered by either bounded pass above warrants deeper tracing
  than it affords,
  [`distributed-systems-deepening.md`](distributed-systems-deepening.md)
  per the "Domain-specific deepening pass" below.
- **Data / persistence** — signal: a schema, migration, stored
  representation, or the durable shape of data written or read by the
  change. Base reasoning: does the change preserve read/write compatibility
  with existing stored data and existing readers/writers of it. Depth
  owner: "Existing behavior ownership" below, and "Findings beyond the
  changed lines" in [`evidence.md`](evidence.md) for readers/writers outside
  the diff, and, when the evidence gathered by this dimension's base
  reasoning warrants deeper tracing than that bounded pass affords,
  [`database-migration-deepening.md`](database-migration-deepening.md) per
  the "Domain-specific deepening pass" below.
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
  is unavailable. Depth owner: "Dependency / supply-chain deepening
  review" below, for materially implicated dependency/build/supply-chain
  semantics specifically.
- **Security / trust boundaries** — signal: a value crosses from a less
  trusted context into a more trusted one, or the change touches
  authentication, authorization, or a policy-enforcement decision. Base
  reasoning: is the boundary still enforced at the point that actually
  matters, for every path that can reach it. Depth owner: "Architectural
  placement and execution-lifecycle fidelity"'s authorization/
  permission-enforcement trigger, and, when the evidence gathered there
  warrants deeper tracing than that bounded pass affords,
  [`security-deepening.md`](security-deepening.md) per the "Domain-specific
  deepening pass" below.
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
  call sites are followed, and, when the evidence gathered by this
  dimension's base reasoning warrants deeper tracing than that bounded pass
  affords, [`performance-deepening.md`](performance-deepening.md) per the
  "Domain-specific deepening pass" below.

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

## Domain-specific deepening pass

Once "Semantic change-implication reasoning" above has identified a
materially implicated dimension, this pass decides whether the evidence
already gathered justifies going further with domain-specific reasoning,
and how 0..N such deepening capabilities compose into one review. The
activation rule (evidence-driven, never a file-type/path/framework
router), the composition and cascading-activation model (bounded by
[`repository-expansion.md`](repository-expansion.md)'s existing
expansion/stop-condition contract), the orthogonality to
[`remediation-scope-boundary.md`](remediation-scope-boundary.md)'s
remediation-required reasoning, and the additive-only rule for explicit
user focus are owned by
[`specialist-depth.md`](specialist-depth.md) and are not restated here.
That activation predicate is decidable entirely from this base pass's
own resident evidence above — evaluating it never requires opening
`specialist-depth.md` — and fails closed: ambiguity or evaluation
failure loads the capability rather than skipping it, per
`specialist-depth.md`'s "Conditional loading: fail-closed."

This is not a second scope model: a domain-specific deepening capability
never decides whether a dimension is considered at all — that obligation
stays with the base pass above, unconditionally — and it introduces no
new finding/severity/evidence schema; every finding it contributes still
passes through [`severity.md`](severity.md), [`evidence.md`](evidence.md),
and the remediation-scope-boundary pass exactly like any other finding.

## Null-like absence-risk review

Inspect changed data-flow and control-flow for credible **null-like
absence** risk whenever the reviewed language admits that failure mode at
all — a **semantic rule keyed to the reviewed language's nullability
model, never a regex or keyword match**. The credible-absence-path
patterns, the interoperability and escape-hatch boundaries that weaken a
language's normal null-safety guarantees, and the suppression rule for a
value already made safe by a guard, the type system, a framework/contract
guarantee, or upstream validation are owned by
[`null-absence-risk.md`](null-absence-risk.md) and are not restated here.

This section adds no new finding category: a surfaced risk is classified
under [`severity.md`](severity.md) and evidenced per
[`evidence.md`](evidence.md) exactly like any other finding, and carries
no dedicated severity merely because a nullable value is present.

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

## Remediation-scope boundary pass

For every material finding, after severity is derived, reason
independently about how much of its remediation the current task/PR
boundary must absorb versus what belongs to separate follow-up work. The
three-part reasoning sequence (validity/severity → remediation-required →
remediation-scope-boundary), the never-widens/never-shrinks-severity rule,
and the worked examples are owned by
[`remediation-scope-boundary.md`](remediation-scope-boundary.md) and are
not restated here.

This is not a second scope model: severity, finding identity, and the
mechanical decision derivation are unchanged. Review depth — how much a
reviewer reasons about a finding's broader implications — must never, by
itself, expand what the current change is required to implement; nor may
the current change's size discourage reporting or reduce the severity of
a valid finding whose full remediation is legitimately out of scope.

## Failure state, retry safety, and recovery

Treat this as one reasoning move, not three separate checklist items,
signal-triggered by a concrete diff shape — more than one side-effecting
step, an entry point that can plausibly run again for the same logical
operation, or an external call combined with a state mutation. The trigger
conditions, the reasoning sequence once triggered (stranded state,
already-happened side effects, safe re-execution, and evidenced-not-assumed
recovery/reconciliation), and the applicability-gated observability
hierarchy (an established metrics/alerts mechanism, then logs, then a
fail-closed high-impact-undiagnosable-failure bar) are owned by
[`failure-retry-recovery.md`](failure-retry-recovery.md) and are not
restated here.

This is not a second scope model: absent a triggering signal this pass
does not apply and requires no action; findings, evidence, and severity
are governed by [`evidence.md`](evidence.md) and
[`severity.md`](severity.md) exactly like any other finding.

## Architectural placement and execution-lifecycle fidelity

Local functional correctness is often insufficient to determine whether a
change is correctly *placed*. A changed method or file can be internally
correct while sitting at the wrong point in the surrounding execution
flow: a decision made after the lifecycle phase that owns it, a check
duplicated below the layer that already performs it, a mutation done
before the precondition that should gate it. The semantic-risk trigger
vocabulary (control flow, side effects, retry/error propagation,
transaction boundaries, authorization, routing/dispatch, idempotency,
state-mutation ordering, lifecycle bookkeeping, resource ownership,
concurrency, and caller/callee contracts), the bounded ring-by-ring context
expansion, the stop conditions — including that **"insufficient evidence"
is a valid terminal outcome** — the ineligible-versus-must-execute-and-fail
distinction, the guardrails, and the evidence requirement for a placement
finding are owned by
[`architectural-placement.md`](architectural-placement.md) and are not
restated here.

This is one concrete application of the proportional-scope and
evidence-labeling rules this repository already defines — "Related changes
as one unit" and "Existing behavior ownership" above, and
[`evidence.md`](evidence.md), "Findings beyond the changed lines." It does
**not** introduce a second scope model or a second evidence standard:
blast radius, evidence labeling (confirmed defect / credible engineering
risk / optional improvement), and the no-repository-wide-audit boundary are
unchanged.

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
contract type is a diff-level signal; it is never itself the finding. The
compatible/breaking/context-dependent classification for each recognized
change shape, the fail-closed rule for an unresolvable consumer surface,
and its relationship to the other API/integration-contract depth owners
are owned by
[`api-contract-compatibility.md`](api-contract-compatibility.md) and are
not restated here.

This section adds no new severity, finding category, or probability
score: a breaking-shape finding is labeled confirmed defect / credible
engineering risk per [`evidence.md`](evidence.md) like any other finding,
and classified per [`severity.md`](severity.md) — a consumer-facing
contract break is typically P1. It is not a second scope model, and it
duplicates neither a schema linter nor a SAST tool: it is one concrete
depth owner, for schema/contract backward compatibility specifically, of
the "API / integration contracts" dimension in "Semantic
change-implication reasoning" above — alongside, not replacing,
"Affected-test / test-impact analysis" above and "Architectural placement
and execution-lifecycle fidelity"'s caller/callee-contract trigger.

## Dependency / supply-chain deepening review

Signal: the change modifies a dependency manifest or lockfile (for example
`package.json`/`package-lock.json`, `requirements.txt`/`poetry.lock`/
`Pipfile.lock`, `go.mod`/`go.sum`, `Cargo.toml`/`Cargo.lock`, `pom.xml`/
`build.gradle`), a container base-image reference (a Dockerfile `FROM`
line), or a CI/automation action reference (a GitHub Actions workflow's
`uses:` line or equivalent). Recognizing that one of these files changed
is a diff-level signal only — it is never itself the finding: a manifest,
lockfile, build file, or package-related filename changing does not by
itself activate this pass; the change's own evidence still has to show one
of the concern areas below before anything is reported.

Concern areas — each requires its own evidence before a finding is
raised, never merely because the qualifying file changed:

- **Major-version compatibility** — a dependency bump crosses a
  semver-major (or ecosystem-equivalent) boundary. Flag when the diff's
  own evidence — a changelog or release-notes reference present in the
  change, a known breaking change for that dependency, or call sites in
  the diff still using an API the new major version removed or altered —
  shows the bump requires an adaptation the diff does not make.
- **Runtime/platform requirement changes** — the minimum language,
  runtime, or platform version is raised (an `engines` field, a
  `requires-python`, a Dockerfile base-image tag, a CI runner or toolchain
  version). Flag when the codebase or its build/CI configuration still
  depends on a feature or behavior unavailable at the new minimum, or when
  the change silently narrows the versions the repository claims to
  support.
- **Dependency expansion** — a lockfile diff adds materially more
  transitive dependencies than the direct manifest change would explain.
  Flag when the expansion is disproportionate and unexplained by the
  change's own evidence — never merely because a lockfile was
  regenerated; a routine patch-level bump's incidental lockfile churn is
  not itself a finding.
- **Provenance / trust and unpinned automation references** — a CI action
  or automation reference is pinned to a mutable ref (a branch or
  floating-tag alias) instead of an immutable commit SHA where the
  repository's own existing convention pins other references that way, or
  a dependency's source changes (its registry, or a registry package
  replaced by a git/URL dependency) in a way that changes who is trusted
  to publish it. Flag when the change's own evidence shows the reference
  or source is less verifiable than what the repository already relies on
  elsewhere — never merely because a `uses:` line or source URL changed.
- **Build/runtime incompatibility** — a build-file change (Dockerfile,
  `build.gradle`, `pom.xml`, a compiler/toolchain pin) changes the
  compiler, toolchain, or runtime version code is built or run with, where
  the code's own evidence — syntax or an API it uses — is incompatible
  with that version.

Fail-closed on an unrecognized manifest, lockfile, or build-file format:
when the format cannot be parsed or understood well enough to reason about
any concern area above, this pass raises no speculative finding for it —
mirrors, and does not replace, the same fail-closed discipline "API /
contract compatibility review" and "Architectural placement and
execution-lifecycle fidelity" above already apply to insufficient
evidence, not a new evidence standard invented for this section alone.

This section adds no new severity, finding category, or score: a
dependency/supply-chain finding is labeled confirmed defect / credible
engineering risk per [`evidence.md`](evidence.md) like any other finding,
and classified per [`severity.md`](severity.md) exactly like any other
finding. Per [`evidence.md`](evidence.md), "Findings beyond the changed
lines," the search for affected call sites or usages scales with the
change's actual blast radius — never a repository-wide dependency audit.

This is not a second scope model, and it is not a generic
dependency-update linter or a vulnerability/CVE scanner: it is one
concrete depth owner, for materially implicated dependency/build/
supply-chain semantics specifically, of the "Infrastructure / deployment"
dimension in "Semantic change-implication reasoning" above. A manifest,
lockfile, Dockerfile, or package-related filename changing is never by
itself sufficient to engage this pass — activation follows the same
evidence-driven composition [`specialist-depth.md`](specialist-depth.md)
defines, never a file-type or path router. It does not resolve or install
dependencies, does not duplicate a dedicated vulnerability/SCA scanner or
CVE feed, and does not enforce a dependency policy this repository has not
itself defined. The recognized manifest/lockfile/build-file inputs, their
diff-recognition detail, and the smallest useful first implementation are
the dependency/supply-chain deepening model design record (a
repository-development document, named here, not linked because it is not
a packaged resource).

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
are not restated here. Recognizing which trigger type a change plausibly
implicates, and confirming whether the interface/contract,
migration/schema, or config-consumer triggers fire, are all decidable
entirely from this base pass's own resident trigger catalog above; only
confirming whether the call-site trigger fires can require
`repository-expansion.md`'s own ring-1 investigation, and an inconclusive
or not-yet-investigated call-site firing determination fails closed: it
loads the capability rather than skipping it, per
`repository-expansion.md`'s "Conditional loading: fail-closed."

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
restated here. That threshold measurement is decidable entirely from this
base pass's own resident diff-size count above — evaluating it never
requires opening `large-pr-partitioning.md` — and fails closed: ambiguity
or evaluation failure loads the capability rather than skipping it, per
`large-pr-partitioning.md`'s "Conditional loading: fail-closed."

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
