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
