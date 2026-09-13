# Policy — Review Reasoning

Governs how `github-pr-review` reasons about a PR's changes once scope is
established. Canonical index: [`github-review.md`](github-review.md). This
reasoning applies only after review authority
([`review-authority.md`](review-authority.md)) and reviewer-mode resolution
([`reviewer-delta-review.md`](reviewer-delta-review.md)) have already run — it
never determines whether or how much of the PR is in scope, only how that
already-established scope is analyzed.

The reasoning-quality invariants below are owned once, in this Skill's shared
[`review-scope.md`](../../../shared/policies/review-scope.md) and
[`evidence.md`](../../../shared/policies/evidence.md) policies, and shared
identically with `local-code-review` so both Skills apply one review-quality
standard — this file does not restate their full text. What follows is this
Skill's own PR-specific application: where each invariant fits in the PR
review flow, and light fallback guidance for a reviewing engine with no
native full-codebase context.

## Semantic Implication Review

Before applying the reasoning passes below, apply
[`review-scope.md`](../../../shared/policies/review-scope.md), "Semantic
change-implication reasoning" — the base pass that detects which
system-level dimensions the PR's own evidence materially implicates and
performs the minimum bounded reasoning for each. That shared section owns
the canonical dimension list, each dimension's activation signal and depth
owner, the not-mutually-exclusive taxonomy, and the bounded-expansion and
stop-condition reuse; this PR-specific policy does not restate them. It is
one application of the existing proportional-scope and evidence rules, not
a second scope model, and its base obligation is unconditional with
respect to any domain-specific deepening capability — the reasoning passes
below may add further depth to a dimension it already activates when
materially warranted, but none of them gates, weakens, narrows, or
replaces it.

## Domain-Specific Deepening Review

For each dimension "Semantic Implication Review" above activates, apply
[`review-scope.md`](../../../shared/policies/review-scope.md),
"Domain-specific deepening pass" (canonical home:
[`specialist-depth.md`](../../../shared/policies/specialist-depth.md)):
decide from the evidence already gathered whether that dimension's
bounded base reasoning already suffices or deeper domain-specific
investigation is warranted, and, when it is, let the relevant
capabilities compose into this one review. That shared policy owns the
evidence-driven activation rule, the 0..N composition and cascading-
activation model (bounded by
[`repository-expansion.md`](../../../shared/policies/repository-expansion.md)),
and the orthogonality to
[`remediation-scope-boundary.md`](../../../shared/policies/remediation-scope-boundary.md);
this PR-specific policy does not restate them. It never decides whether a
dimension is considered at all — that stays with the base pass above —
and it introduces no new finding/severity/evidence schema.

## Null-Like Absence-Risk Review

Apply [`review-scope.md`](../../../shared/policies/review-scope.md),
"Null-like absence-risk review," to the PR's changed data-flow and
control-flow whenever the reviewed language admits a null-pointer,
`undefined`/`null`, `nil`, or `None` absence failure. That shared section
owns the cross-language semantic rule (never a regex or keyword match),
the credible-absence-path patterns, the interoperability/escape-hatch
boundaries, and the suppression rule for guarded, type-guaranteed, or
upstream-validated values; this PR-specific policy does not restate them.
It introduces no new finding category or severity — a surfaced risk is
classified and evidenced exactly like any other finding.

## Logical Cohort Review

The durable invariant — review related changes together rather than treating
files or hunks as isolated units — is owned by
[`review-scope.md`](../../../shared/policies/review-scope.md), "Related
changes as one unit." Apply it to this invocation's complete established
scope: the full diff for a normal review, or the bounded delta plus
surrounding context for a delta re-review (see
[`reviewer-delta-review.md`](reviewer-delta-review.md), "Same reviewer: delta
boundary and scope"). No PR-specific grouping mechanics beyond that shared
invariant are prescribed here.

## Root-Cause and Model-Completeness Review

When related candidate findings indicate one shared mechanism, apply
[`root-cause-consolidation.md`](../../../shared/policies/root-cause-consolidation.md),
"Root-cause and model-completeness pass" (routed from
[`review-scope.md`](../../../shared/policies/review-scope.md)), before
finalizing findings. That shared section owns
the trigger, structural-vs-separate finding rule (including consolidating one
shared cause into a single authoritative finding with a required, exhaustive
affected-locations list of at least two sites, and the fail-open to separate
findings when the shared cause is not positively established),
model-completeness questions, canonical-owner and external-package guidance,
evidence requirements, and how re-review reconciles the prior finding set;
this PR-specific policy does not restate them. On a re-review, whether prior
per-site finding identities fold into the consolidated finding is governed by
[`stateful-delta-rereview.md`](stateful-delta-rereview.md) (§3, the
`CONSOLIDATED` disposition — positive root-cause evidence only, never `N→1`
topology, and it resolves nothing), which this policy also does not restate.
A consolidated cross-path finding is placed per
[`finding-placement.md`](finding-placement.md) — one body finding, not one
inline comment per affected call path.

## Remediation-Scope Boundary Review

For every material finding, before finalizing, apply
[`remediation-scope-boundary.md`](../../../shared/policies/remediation-scope-boundary.md)
(routed from
[`review-scope.md`](../../../shared/policies/review-scope.md)): reason
independently about whether remediation is required for the current PR
and, when it is, how much of it belongs inside the current PR boundary
versus a separate `Follow-up`. That shared policy owns the three-part
reasoning sequence, the never-widens/never-shrinks-severity rule, and the
worked examples; this PR-specific policy does not restate them. It runs
after severity is derived per [`severity.md`](../../../shared/policies/severity.md)
and after root-cause consolidation above, and it changes nothing about
severity, finding identity, or the mechanical decision derivation — a
blocking P0/P1 still blocks on its bounded `Fix` even when a related
broader concern exists as a `Follow-up`.

## Architectural Placement Review

When a PR change plausibly affects a semantic-risk category listed there —
control flow, side effects, retry/exception behavior, transaction
boundaries, authorization, routing/dispatch, idempotency, state-mutation
ordering, or another lifecycle contract — apply
[`review-scope.md`](../../../shared/policies/review-scope.md),
"Architectural placement and execution-lifecycle fidelity," before
finalizing findings. That shared section owns the triggers, the bounded
caller/callee/owning-boundary expansion ladder, the stop conditions, the
ineligible-versus-must-execute-and-fail distinction, and the both-locations
evidence requirement; this PR-specific policy does not restate them. It is
one application of the existing proportional-scope and evidence rules, not
a second scope model.

## Code Impact / Dependency Analysis

The durable invariant — a finding located outside the changed lines is valid
only when the PR introduces, activates, exposes, breaks, or materially
affects it, never as an unrelated pre-existing-defect audit, scaled to the
change's realistic blast radius — is owned by
[`evidence.md`](../../../shared/policies/evidence.md), "Findings beyond the
changed lines."

When the reviewing engine has no native full-codebase or cross-reference
capability, bound dependency exploration to callers, callees, interface
implementations, event producers/consumers, and tests directly relevant to a
changed symbol, contract, or schema, using ordinary repository search — stop
once that is enough to judge the PR's correctness. No dedicated code-graph
tool or vendor capability is required for this analysis.

Findings produced from this reasoning still require concrete evidence per
[`evidence.md`](../../../shared/policies/evidence.md) and
[`../../../shared/templates/finding.md`](../../../shared/templates/finding.md)
— a dependency relationship is relevant to a finding only when it demonstrates
a concrete defect, regression, contract violation, or other actionable issue,
never merely because a dependent file or symbol exists.

## Affected-Test Impact Review

When a PR changes observable production behavior — a changed return value,
status, error, or emitted event; an altered calculation, validation, or
state-transition rule; a new or removed branch; or a modified public
contract — apply
[`affected-test-analysis.md`](../../../shared/policies/affected-test-analysis.md),
"Affected-test / test-impact analysis" (routed from
[`review-scope.md`](../../../shared/policies/review-scope.md)), before
finalizing findings. That
shared section owns the trigger, the located-test re-validation and new-path
coverage steps, the read-only boundary (inspect test code as text; never run
the target repository's tests), the not-"did the PR add tests?" framing, and
the evidence and no-repository-wide-audit limits; this PR-specific policy
does not restate them. It is one application of the existing
proportional-scope and evidence rules, not a second scope model.

When the reviewing engine has no native cross-reference capability, bound the
search to tests reachable by ordinary repository search from a changed
symbol, endpoint, message/event type, error type, or shared fixture, and stop
once that is enough to judge regression risk.

## API / Contract Compatibility Review

When a PR changes a repository contract another component consumes — an
OpenAPI/JSON Schema/protobuf definition, a public API request/response
model, an event/message schema, or a configuration contract — apply
[`review-scope.md`](../../../shared/policies/review-scope.md), "API /
contract compatibility review." That shared section owns the recognized
contract types, the compatible / breaking / context-dependent
classification for each change shape, the fail-closed rule for an
unresolvable consumer surface, and the reuse of the existing evidence and
severity model; this PR-specific policy does not restate them. It is one
concrete depth owner of the "API / integration contracts" dimension
activated by "Semantic Implication Review" above, alongside — never
replacing — this file's own "Affected-Test Impact Review" and
"Architectural Placement Review," and it is not a second scope model.
