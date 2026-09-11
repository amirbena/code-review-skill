# ARCHITECTURE.md

The conceptual architecture of this repository's two Code Review Agent
Skills: the components, how they relate, the review lifecycle, and the
boundaries and invariants that hold across both. It is decoupled from any
specific runtime — see [`AGENTS.md`](../AGENTS.md) ("Global invariants" —
runtime neutrality; the **Agent via Skill** vocabulary) and
[`policies/skill-development-policy.md`](../policies/skill-development-policy.md),
"Portable Core, Optional Runtime Adapters."

This document is a **map, not a contract**. Exact behavioral semantics
live in the canonical policies and runbooks it links; user-facing usage
guidance for optional capabilities lives in
[`docs/features/`](features/README.md). For *why* these Skills exist
alongside native and third-party reviewers, see
[`CODE_REVIEW_COMPARISON.md`](CODE_REVIEW_COMPARISON.md).

## The mental model in one picture

```text
                     Shared Review Standard
             (shared/policies/ — scope, severity, evidence,
              review-context, review-evidence, ownership)
                              │
              ┌───────────────┴───────────────┐
              │                               │
      local-code-review                github-pr-review
              │                               │
   Review target: local Git delta   Review target: GitHub PR delta
   (committed / staged / unstaged /  (full diff, or a bounded
    untracked, detected separately)   reviewer-owned delta re-review)
              │                               │
   Delivery: one structured report   Delivery: a report (passive), or
   returned to the caller             inline comments + summary +
                                      Approve / Request Changes (active)
```

Everything in the top box is **one copy**, consumed identically by both
Skills, so P0/P1/P2 semantics never diverge. Everything below the split is
**target-specific**.

### What is shared vs. what differs

| Concern | Shared (one copy under `shared/`) | Differs per Skill |
|---|---|---|
| Review reasoning | scope, correctness, regression, architecture, behavioral heuristics | — |
| Severity | the P0/P1/P2 model and the mechanical blocking rule | only the decision *labels*: `REVIEW CLEAN` / `CHANGES REQUIRED` vs. `Approve` / `Request Changes` |
| Context model | review target / review context / repository context / existing review evidence | a thin per-Skill application (the local delta vs. the PR) |
| State inspection | — | local Git state vs. GitHub PR state |
| Delivery | the canonical report and finding shapes | a local report vs. GitHub publication |
| Extra machinery | — | `github-pr-review` only: temporary checkout, parallel workers, self-review mutation boundary, review-action authorization, SHA-bound delta re-review, optional machine-readable status |

### Where to read next

Each numbered section is self-contained — jump to what you need.

| To understand… | Read |
|---|---|
| which file owns what, and how it maps into an archive | §1 Module Map, §7 Packaging |
| the review-target / review-context / evidence vocabulary | §1, and §2 "Normalize Inputs" |
| the end-to-end review pipeline | §2 Core Pipeline |
| who owns policy vs. runbook vs. output | §1 "Thin runbooks", §3, §9 |
| what the caller owns and the Skill does not | §4 Orchestration Boundary, §5 Handoff |
| what is deliberately not built | §2 "Future work" |
| how to invoke an optional capability as a user | [`docs/features/`](features/README.md) |

## 1. Module Map

```text
                 shared/
            review policies
                  │
         ┌────────┴────────┐
         │                 │
local-code-review    github-pr-review
         │                 │
 local report        GitHub delivery
```

`shared/` holds one copy of every rule both Skills apply. Neither Skill
owns a copy of the severity model, evidence requirements, review-scope
rules, or the context / evidence model.

| Location | Owns | Canonical detail |
|---|---|---|
| [`shared/policies/`](../shared/policies/README.md) | portable review semantics used identically by both Skills | scope, change-risk signal / review-depth classification, repository-expansion triggers and bounds, large-PR partitioning, root-cause consolidation, affected-test analysis, severity, evidence, repository-instruction discovery, git-safety, review-ownership, review-context, requirement coverage, jira-context, review-evidence, runtime-validation, parallel-review, file-reviewability, invocation-options |
| [`shared/templates/`](../shared/templates/) | the canonical finding and review-summary shapes; each delivery surface renders one projection of them | [`finding.md`](../shared/templates/finding.md) (field contract), [`finding-rendering.md`](../shared/templates/finding-rendering.md) (rendering exemplars), [`review-summary.md`](../shared/templates/review-summary.md) |
| [`skills/local-code-review/`](../skills/local-code-review/SKILL.md) | local-Git-specific rules with no PR analogue | invocation approval, repository-state categories + staged-delta fingerprint, thin local applications of the shared context / prior-evidence model |
| [`skills/github-pr-review/`](../skills/github-pr-review/SKILL.md) | GitHub-delivery rules with no local analogue, indexed from [`policies/github-review.md`](../skills/github-pr-review/policies/github-review.md) | review authority + self-review mutation boundary, [review-action authorization](../skills/github-pr-review/policies/review-action-authorization.md), reviewer delta re-review, PR scope + pagination, repository-backed checkout, finding placement, batched publication + ordering, optional [machine-readable review status](../skills/github-pr-review/policies/review-status-enforcement.md) |

The optional review context accepts, uniformly, free-form requirements,
explicit user instructions, a Jira/tracker ticket, an explicitly supplied
GitHub Issue (no automatic PR↔Issue discovery), an HLD/ADR, or an
implementation plan — see
[`shared/policies/review-context.md`](../shared/policies/review-context.md).
When that context contains authoritative requirements or acceptance criteria,
the shared
[`requirement-coverage.md`](../shared/policies/requirement-coverage.md) policy
adds an evidence-backed per-requirement assessment and a task-relative
complete/incomplete signal; it remains independent of finding severity and the
review decision.

Every review also runs the always-on
[`change-risk-signals.md`](../shared/policies/change-risk-signals.md) pass: a
fixed catalog of change-risk signals (auth/access-control, migration/schema,
concurrency, public API contract, sensitive path, infra/config, diff size)
maps deterministically to one `standard` / `elevated` / `deep` review-depth
level that is emitted in the review's subordinate metadata. Paired with it,
the always-on
[`repository-expansion.md`](../shared/policies/repository-expansion.md) pass
evaluates a fixed catalog of expansion triggers (call site, interface/
contract, migration/schema, config consumer) and, for each one that fires,
follows it through a bounded, ring-based procedure whose ceiling is scaled
by that same depth level — reported the same way, in the same subordinate
metadata. It makes the informal "scale to blast radius" guidance
inspectable; neither pass is a second scope model, a finding, or a merge
gate.

When a change's diff size reaches a fixed, separate threshold — double
`change-risk-signals.md`'s own `deep` threshold — the conditional
[`large-pr-partitioning.md`](../shared/policies/large-pr-partitioning.md)
pass activates: it builds coherent review units by a deterministic
directory-seed / evidence-based coherence-merge / size-cap procedure,
reviews each unit against the unchanged shared policy stack, then
aggregates and de-duplicates the units' findings (including
cross-partition root-cause consolidation) into the one final review. A
change under the threshold is unaffected and reviewed as a single unit as
before. What the depth level changes about review stopping criteria
remains owned by that separate, still-open concern, not by this
classification.

### Thin runbooks, canonical policy owners

A runbook is an execution document, not a second policy store — see
[`policies/skill-development-policy.md`](../policies/skill-development-policy.md),
"Runbook Design." It defines flow, phase ordering, and which policy
governs each phase; it does not restate that policy's decision tables or
edge-case semantics.

```text
Shared policy (shared/policies/)      → reusable review semantics, identical across both Skills
Skill-specific policy (skills/<name>/policies/) → semantics unique to that Skill
Runbook (skills/<name>/runbooks/)     → execution flow and phase ordering only; each step
                                        names the policy that governs it
```

`skills/local-code-review/runbooks/local-review.md` and
`skills/local-code-review/policies/repository-state.md` are the clearest
example: Git category detection, push/sync status, and the
staged-fingerprint contract live entirely in the policy; the runbook
states only when each is applied.

## 2. Core Pipeline (per Skill)

Every review — either Skill, either delivery mode — runs three phases:

1. **Resolve inputs** — turn the invocation into normalized presentation
   options, a Review Target, optional Review Context, Repository Context,
   and optional Existing Review Evidence. Nothing below the target ever
   widens it.
2. **Reason** — inspect state read-only, compute the exact delta,
   optionally prepare a repository-backed checkout, plan sequential or
   parallel execution, produce candidate findings, then reconcile them
   centrally.
3. **Decide and deliver** — one aggregator applies the shared severity
   model to produce one P0/P1/P2 set and one decision, rendered as a
   local report or a GitHub review.

The stage diagram below expands those phases. It is conceptual reading
order, not a required implementation shape; repository-backed modes and
parallel workers apply to `github-pr-review` only.

```text
Review Invocation
    ↓
Resolve External Context
    ├── Jira MCP / connector        (only when a Jira reference is supplied;
    │                                read-only; unresolved → JIRA CONTEXT
    │                                UNRESOLVED, stop — no key/branch inference)
    ├── explicit GitHub Issue context (reference → read-only GitHub, or
    │                                  pasted text; no auto PR↔Issue discovery)
    └── supplied free-form context    (consumed directly, no resolution)
    ↓
Normalize Inputs
    ├── Review Target        (local delta | GitHub PR delta — never widened below)
    ├── Review Context       (optional: user instructions / resolved Jira /
    │                         GitHub Issue / HLD / ADR / plan / PR description)
    ├── Repository Context   (repository snapshot / API-accessible files;
    │                         applicable AGENTS.md hierarchy; policies;
    │                         architecture/docs; surrounding code; tests/config)
    └── Existing Review Evidence (optional: prior findings, resolved
                                  findings, settled decisions, prior comments)
    ↓
Git / GitHub State Inspector          (read-only)
    ↓
Review Delta Resolver
    ↓
Prepare Repository Context
    ├── GitHub/API-only mode              (no checkout; the only mode for local review)
    ├── Temporary repository-backed mode  (github-pr-review; isolated, read-only,
    │                                      detached checkout at head_sha)
    ├── Optional repository-backed enrichment (failure → visible API-only degradation)
    └── Required repository-backed review     (failure → REVIEW INCOMPLETE, no workers)
    ↓
Resolve changed files and one normalized per-file AGENTS.md hierarchy
    ↓
Plan Review Execution
    ├── Sequential                   (default and always valid)
    └── Parallel only with capability + at least two materially independent
          dimensions + expected latency benefit (read-only workers,
          same PR base/head snapshot; execution optimisation only)
    ↓
Review workers  (each: identical normalized inputs + one assigned dimension
                 → candidate findings only; never publish, never decide)
    ↓
Reconcile findings  (normalize → deduplicate → reconcile overlapping/
                     conflicting → canonical severity)
    ↓
Shared Review Semantics  (shared/policies/)
    ├── scope validation (incl. scope-boundary reasoning against context)
    ├── optional runtime validation evidence — declared command and/or targeted
    │   per-finding reproduction (shared/policies/runtime-validation.md)
    ├── correctness / regression / architecture invariants
    └── severity classification  (shared/policies/severity.md)
    ↓
Canonical final decision  (one aggregator; worker order never matters;
                           required dimension missing → REVIEW INCOMPLETE)
    ↓
Skill-Specific Output
    ├── local-code-review  → structured report (always)
    └── github-pr-review   → Passive Report | Active GitHub Review
    ↓
Cleanup  (github-pr-review: remove the temporary checkout on every exit
          path — success, failure, interruption — guarded delete only)
```

### Stage responsibilities

Each stage below names its canonical owner rather than restating the
rule.

- **Resolve External Context** — turn *references* into normalized
  context before review reasoning:
  [`shared/policies/review-context.md`](../shared/policies/review-context.md),
  "Jira context resolution" and "Reference-based context." Free-form text
  is consumed directly; a Jira reference runs the shared numbered
  resolution procedure (read-only) or returns `JIRA CONTEXT UNRESOLVED`;
  a GitHub Issue reference resolves through read-only GitHub or pasted
  text. Jira is never mandatory.
- **Normalize Inputs** — separates the four concepts owned by
  [`review-context.md`](../shared/policies/review-context.md) and
  [`review-evidence.md`](../shared/policies/review-evidence.md): the
  **review target** (never widened), optional **review context**,
  **repository context**, and optional **Existing Review Evidence**
  (reconciled against the *current* target, never inherited). Missing
  optional inputs change nothing. Supplied review context carries typed
  authority — authoritative vs. informational — per the contextual-evidence
  model ([`review-context/contextual-evidence-model.md`](review-context/contextual-evidence-model.md),
  #118); an informational source never silently overrides an explicit
  requirement or an approved decision, and a finding may record the
  contextual evidence that informed it.
- **Git / GitHub State Inspector** — read-only inspection of Git state
  and, for `github-pr-review`, GitHub state (PR metadata, base/head SHA,
  checks, prior reviews with their state, review/issue comments, thread
  resolved state), retrieved paginated-to-exhaustion. Never mutates.
- **Review Delta Resolver** — computes exactly what must be reviewed: the
  committed / staged / unstaged / untracked delta (local), or the PR's
  full or bounded-delta diff (GitHub).
- **Prepare Repository Context** — API/working-tree reads by default. In
  optional or required repository-backed mode
  ([`repository-checkout.md`](../skills/github-pr-review/policies/repository-checkout.md)),
  `github-pr-review` also materialises an isolated, read-only, detached
  checkout at the immutable PR `head_sha`; the PR delta stays
  `merge-base(base,head)..head`; no target-repository code runs.
- **Repository Instruction Resolver** — resolve applicable root-to-specific
  `AGENTS.md` chains once from the same snapshot
  ([`repository-instructions.md`](../shared/policies/repository-instructions.md));
  the mapping goes unchanged to sequential execution or every worker and
  never widens the target.
- **Plan Review Execution** — sequential by default; parallel read-only
  workers only with a detected runtime capability **and** two materially
  independent dimensions **and** expected latency benefit
  ([`parallel-review.md`](../shared/policies/parallel-review.md)).
  Sequential and parallel runs must reach the same findings and decision;
  the Skill never mutates user configuration to obtain a capability.
- **Review workers** — each gets one bounded, normalized input and its
  own dimension, and returns **candidate findings only** — never
  publishes, never derives the decision, never sees another worker's
  output.
- **Reconcile findings** — one centralized stage: normalize → deduplicate
  (same location + normalized claim; carry the higher candidate severity,
  report once) → reconcile overlapping/conflicting. Worker completion
  order never affects the result.
- **Shared Review Semantics** — the single reasoning model in
  [`review-scope.md`](../shared/policies/review-scope.md), plus optional
  runtime-validation evidence
  ([`runtime-validation.md`](../shared/policies/runtime-validation.md)) —
  a declared-command run and/or a targeted per-finding reproduction, each
  adding evidence only: a validation run never rewrites a finding or the
  decision, and a finding's `reasoned` / `runtime-confirmed` /
  `attempted-inconclusive` state is provenance, not a severity input.
- **Canonical final decision** — only the aggregator applies
  [`severity.md`](../shared/policies/severity.md)'s mechanical derivation:
  one P0/P1/P2 set and one `REVIEW CLEAN` / `CHANGES REQUIRED` (local) or
  `Approve` / `Request Changes` (GitHub). A missing required dimension
  yields `REVIEW INCOMPLETE` — never a clean/approved result.
- **Skill-Specific Output** — the delivery adapter never changes the
  underlying findings or severities. `github-pr-review`'s active
  publication and any Approve/Request Changes stay the aggregating
  reviewer's, once.
- **Cleanup** — `github-pr-review` removes any temporary checkout on
  every exit path with a guarded delete (inside the scratch parent, not
  the parent itself, ownership marker present).

### Optional capabilities

Capabilities layered on the core pipeline — some explicitly opt-in, some
automatically scoped when their precondition holds — each leaving a
coherent Skill when absent or not engaged. Whether each is default,
conditional, or requested is owned by
[`docs/features/`](features/README.md), which also carries usage guidance
for every one of them.

- **Temporary repository-backed GitHub PR review** — opt-in isolated,
  read-only checkout at the PR head; context only
  ([`repository-checkout.md`](../skills/github-pr-review/policies/repository-checkout.md)).
- **Portable parallel review** — opt-in execution optimisation with
  capability detection and a sequential fallback
  ([`parallel-review.md`](../shared/policies/parallel-review.md); runtime
  facts in [`runtime-parallelism.md`](runtime-parallelism.md)).
- **Review-action authorization** — review analysis is separate from
  GitHub mutation authority
  ([`review-action-authorization.md`](../skills/github-pr-review/policies/review-action-authorization.md)):
  a non-mutating `recommendation-only` default, `block-only`, and
  `explicitly-authorized auto-action`; self-review is allowed but
  self-approval is not; a verdict is not authorization and `APPROVE` is
  not merge authority.
- **Optional machine-readable review status** — one stable aggregated,
  exact-HEAD status/check derived from the same canonical verdict
  ([`review-status-enforcement.md`](../skills/github-pr-review/policies/review-status-enforcement.md)).
- **Opt-in `human_review_output` (with its derived companion
  `human_inline_findings`) and `include_fix_prompt`** — presentation
  and remediation options normalized deterministically from a fixed
  vocabulary
  ([`invocation-options.md`](../shared/policies/invocation-options.md)).
- **Stateful delta re-review** — packaged runtime policy in `github-pr-review`
  ([`stateful-delta-rereview.md`](../skills/github-pr-review/policies/stateful-delta-rereview.md),
  Issue #65): when prior GitHub-native review evidence exists, a re-review
  reconciles prior finding/lifecycle state, classifies the current pass
  (unresolved / moved / fixed / reopened / newly introduced / ambiguous /
  consolidated), reconsiders attributable blast radius and settled
  assumptions, and escalates to a full review when the prior state cannot
  seed a safe comparison. It installs the semantics contracted in
  [`findings/delta-re-review-contract.md`](findings/delta-re-review-contract.md)
  (#64), applies the transitions in
  [`findings/finding-lifecycle-contract.md`](findings/finding-lifecycle-contract.md)
  (#62), and reconstructs a Reviewed State Record per
  [`findings/reviewed-sha-state-contract.md`](findings/reviewed-sha-state-contract.md)
  (#63). It installs **no** matching *algorithm* or stable-identity
  constructor — those stay reviewer judgment applying the documented
  discipline. `local-code-review` does not load this policy: it is
  architecturally stateless between invocations.

### Repository-development instrumentation (not packaged)

Contracts and tooling that support developing these Skills. They are
repository-development material — **not** part of either packaged archive,
and no packaged Skill resource depends on them.

- **Contextual-evidence model** — the typed model for using
  caller-supplied context as evidence: every evidence type marked
  authoritative or informational, the authority/non-override rules, the
  deterministic resolution outcomes for conflicting / stale / ambiguous
  context, provenance-aware findings, and the smallest-useful first slice
  ([`review-context/README.md`](review-context/README.md) →
  [`review-context/contextual-evidence-model.md`](review-context/contextual-evidence-model.md),
  #118, with a test-only reference model). Its one packaged touch-point is
  the optional **contextual evidence** field on
  [`../shared/templates/finding.md`](../shared/templates/finding.md); source
  adapters and runtime attachment are deferred — see "Future work" below.
  [#176](https://github.com/amirbena/code-review-skill/issues/176) and
  [#178](https://github.com/amirbena/code-review-skill/issues/178) build on
  it without redefining it.
- **Finding-confidence model** — the one machine-readable evidence-state
  value a finding carries: the closed set `confirmed` / `credible` /
  `runtime-validation-unavailable` / `external-contract-unvalidated` /
  `insufficient-context`, the per-value entry criteria, the mapping that
  rolls the #128 runtime-validation state and the #118 authoritative/
  informational provenance into this one field, the `credible` default, and
  the rule that a lower value never lowers the evidence bar, the severity, or
  the review decision
  ([`finding-confidence/README.md`](finding-confidence/README.md) →
  [`finding-confidence/finding-confidence-model.md`](finding-confidence/finding-confidence-model.md),
  #178, with a test-only reference model). Its one packaged touch-point is
  the optional **confidence** field on
  [`../shared/templates/finding.md`](../shared/templates/finding.md); the #67
  machine-readable output schema wiring is deferred — see "Future work"
  below.
- **Cross-review finding-identity contracts** — the requirements
  ([`findings/finding-identity-requirements.md`](findings/finding-identity-requirements.md),
  #58), the precision-first matching strategy
  ([`findings/finding-matching-strategy.md`](findings/finding-matching-strategy.md),
  #59), and the deterministic descriptor/identity derivation
  ([`findings/finding-stable-identity.md`](findings/finding-stable-identity.md),
  #60, with a test-only reference model) are settled. Their Skill-runtime
  wiring is still open — see "Future work" below. These contracts share
  the [`findings/`](findings/README.md) directory.
- **Code-review quality benchmark** — a repeatable check of whether a
  Skill change improved or regressed review quality against a fixed
  corpus. The single-case machine-readable format is
  [`benchmark/fixture-format.md`](benchmark/fixture-format.md); the initial
  crafted corpus is [`benchmark/corpus/`](benchmark/corpus/README.md); a
  run's per-case isolation, repository-safety invariants, and result shape
  are [`benchmark/runner-contract.md`](benchmark/runner-contract.md);
  produced↔expected pairing is
  [`benchmark/match-criteria.md`](benchmark/match-criteria.md), the
  relation the quality metrics build on —
  [`benchmark/missed-and-incorrect-findings.md`](benchmark/missed-and-incorrect-findings.md)
  (false-negative / false-positive counts),
  [`benchmark/severity-accuracy.md`](benchmark/severity-accuracy.md)
  (over-/under-severity), and
  [`benchmark/duplicate-noise.md`](benchmark/duplicate-noise.md)
  (same-root-cause redundancy) — each rendered alongside the
  regression comparison in
  [`benchmark/regression-report.md`](benchmark/regression-report.md)
  without gating it. Every reference metric under `tests/reference/` is
  test-only; nothing benchmark is packaged. Repository-development docs
  live in the [`benchmark/`](benchmark/README.md) directory.
- **Repository-intelligence model** — the candidate-architecture
  comparison and recommended minimal model for what a fired
  [`repository-expansion.md`](../shared/policies/repository-expansion.md)
  (#87) trigger resolves inside its authorized ring: the typed
  entity/relationship model, provenance, snapshot identity and staleness
  (reject-and-rebuild on mismatch, never silent reuse), and
  relationship-influence attribution
  ([`repository-intelligence/README.md`](repository-intelligence/README.md) →
  [`repository-intelligence/repository-intelligence-model.md`](repository-intelligence/repository-intelligence-model.md),
  #129, with a test-only reference model). It has **no** packaged
  touch-point: #87's trigger catalog, ring ceiling, and reporting contract
  are unchanged, and no finding-template field is added — the eventual
  representation of relationship-influence attribution in the packaged
  finding contract is deferred; see "Future work" below.

### Future work (not implemented)

Deliberately **not** part of the current architecture — no code, policy,
or runbook implements them today:

- **Automatic branch-protection / ruleset configuration beyond the one
  opt-in required-check setup** — `github-pr-review` can add its single
  aggregated status context to a base branch's required checks only
  through an explicit, separately requested setup action that preserves
  every unrelated rule, required check, bypass actor, and
  approval/stale-review setting
  ([`review-status-enforcement.md`](../skills/github-pr-review/policies/review-status-enforcement.md)).
  It never changes approval-count rules,
  `dismiss_stale_reviews_on_push`, `require_last_push_approval`, or bypass
  actors, and never merges.
- **Automatic execution of PR code** — neither Skill runs the target
  repository's tests, linters, build, hooks, or arbitrary commands, even
  in repository-backed mode. Cloning untrusted PR code is not permission
  to execute it.
- **Runtime attachment of the cross-review stable finding identifier** —
  the requirements, the matching strategy, the deterministic
  descriptor/identity derivation, and the two-state lifecycle are all
  settled contracts (see "Repository-development instrumentation" above);
  what is unbuilt is the Skill-runtime wiring. No packaged policy,
  runbook, or code mints or propagates the movement-tolerant identifier
  during a review yet, so distinguishing "the same defect again" from "a
  new defect" across runs stays reviewer judgment applying the documented
  discipline. The stateful delta re-review policy consumes the lifecycle
  vocabulary but installs no matching algorithm or stable-identity
  constructor.
- **Contextual-evidence source adapters and runtime attachment** — the
  contextual-evidence model (#118, "Repository-development instrumentation"
  above) is consumed today as reviewer discipline over context the caller
  already supplies, plus the optional **contextual evidence** finding
  field. No code retrieves, resolves, infers, or auto-attaches contextual
  evidence; there is no Jira / GitHub Issue / Slack / ADR ingestion
  adapter, no automatic PR↔Issue discovery, and no machine-readable
  provenance block in review output (that waits on the #67 output schema).
- **Machine-readable review output schema** — #178 defines the unified
  finding `confidence` field and its values (the finding-confidence model,
  "Repository-development instrumentation" above), and the finding template
  renders it in human output. The #67 JSON-style schema document that would
  carry `confidence`, `severity`, `location`, and the rest as a formal
  contract for machine consumers, and its versioning (#68), are still
  unbuilt.
- **Repository-intelligence retrieval and a packaged relationship-influence
  field** — the repository-intelligence model (#129, "Repository-development
  instrumentation" above) is a design record and a test-only reference
  model only. No code in this repository builds, persists, or queries a
  repository graph; no runtime retrieves entities or relationships during a
  review; [`repository-expansion.md`](../shared/policies/repository-expansion.md)
  (#87)'s trigger catalog, ring ceiling, and reporting contract are
  unchanged. There is no packaged finding field carrying
  `influential_relationships` — that representation is left to a later,
  separately-scoped implementation issue once the model is validated.

## 3. Separation of Concerns

| Concern | Owned by |
|---|---|
| Review reasoning (what's wrong, why, severity) | shared/policies/, consumed identically by both Skills |
| Local Git state inspection | `local-code-review` |
| GitHub state inspection + delivery (comments, Approve/Request Changes) | `github-pr-review` |
| Orchestration (which Skill runs when, loop control, fix application) | the calling workflow / Team Lead — **never** either Skill |
| Implementation ownership (writing/fixing code) | the implementing Agent or developer — **never** either Skill |

## 4. Orchestration Boundary

Neither Skill owns orchestration. The runtime, Team Lead, or implementing
Agent decides when to invoke a Skill, whether to invoke it again, when to
apply fixes, and when to open/update a PR.

```text
Orchestrator → chooses Skill → Skill reviews once → returns result
```

That discretion is bounded two ways, both owned by
[`policies/review-orchestration-policy.md`](../policies/review-orchestration-policy.md):

- **`local-code-review` is never automatic.** Every invocation — the
  first and every re-review after fixes — requires fresh, explicit user
  approval scoped to that one run
  ([`invocation-approval.md`](../skills/local-code-review/policies/invocation-approval.md)).
- **An implementing Agent never reviews its own PR.** Opening/updating
  that PR is the terminal step of the implementation workflow;
  `github-pr-review` is invoked by a genuinely separate reviewer.

The orchestrator owns repetition; the Skill keeps no memory of prior
invocations, which is why `local-code-review` ships no `max_loops`
setting.

## 5. Handoff Between Skills

```text
Implementation Agent (implementation finished, or a fix just applied)
    ↓  ask user: run local-code-review for this run?
    ├── no  → continue without review
    └── yes → Local Code Review Skill (one invocation) → findings → fixes
                 ↓  [no automatic re-run — ask again before another invocation]
local implementation accepted → push / open or update PR → STOP

— separate reviewer / review task —
    ↓
GitHub PR Review Skill  (reviews the PR's actual current state, regardless of history)
```

Each `Local Code Review Skill` box is exactly one invocation gated by its
own fresh approval. A "no" at any gate is fully valid. `github-pr-review`
does not assume `local-code-review` ran; the two are independently
invokable.

## 6. External PR Workflow (`github-pr-review`)

```text
External GitHub PR
    ↓ resolve reviewer identity + PR author (+ controlling authority)
    ↓ inspect authoritative PR HEAD
    ↓ review → inline findings → P0 / P1 / P2
    ↓ permitted Approve / Request Changes event, or explicit formal-review unavailability
    ↓ stop
```

Maximum automated positive action: **Approve**. No merge occurs — see
[`skills/github-pr-review/runbooks/active-pr-review.md`](../skills/github-pr-review/runbooks/active-pr-review.md).

## 7. Packaging: Source Layout vs. Distribution Layout

Source layout and distribution layout are intentionally different:

```text
source repository layout            standalone Skill archive
(skills/<name>/, shared/)                (dist/*.zip)
    ↓                                        ↓
skills/<name>/SKILL.md              →   SKILL.md            (archive root)
skills/<name>/runbooks/…            →   runbooks/…
skills/<name>/templates/…           →   templates/…
skills/<name>/policies/…            →   policies/…
skills/<name>/metadata/…            →   metadata/…
shared/policies/…, shared/templates/…  →  shared/policies/…, shared/templates/…
```

[`scripts/package-manifest.json`](../scripts/package-manifest.json) is the
single source of truth for archive names, copied resources, their archive
destinations, and required-entry guards. `scripts/package-skills.sh` /
`scripts/package-skills.ps1` consume it through the shared containment
validator in `scripts/package_manifest.py` and stage each Skill's files under
`dist/.staging/`, drop the `skills/<name>/` prefix so
`SKILL.md` lands at the archive root, then zip the staged tree's
*contents* into `dist/*.zip`. Because `SKILL.md` moves from source depth 2
to depth 0, its links into `shared/` change from `../../shared/...` to
`shared/...`, and nested files (source depth 3) change from
`../../../shared/...` to `../shared/...`. Packaging applies exactly that
narrow, deterministic text substitution across the staged Markdown —
Skill-internal links are untouched, and the canonical source files remain
the single source of truth.

Repository-development files — `AGENTS.md`, `policies/`, `docs/`
(including this file and everything under [`features/`](features/README.md)),
and the root `README.md` — are **never** packaged, and no packaged Skill
resource may depend on them
([`policies/skill-development-policy.md`](../policies/skill-development-policy.md)).

## 8. Agent Skills Discovery vs. Operational Behavior

```text
SKILL.md frontmatter → Skill discovery (name, description) only — no review policy
SKILL.md body        → core operating instructions (identity, inputs, workflow, boundaries)
shared/policies/, runbooks/, templates/ → detailed rules, procedures, output contracts
```

`skills/<name>/metadata/skill.yaml` is separate package metadata for
consumers outside the Agent Skills discovery path; its
`name`/`description` mirror `SKILL.md`'s frontmatter, and packaging fails
unless they are exactly equal.

## 9. Reasoning vs. Delivery vs. Ownership

- **Review reasoning is Skill-agnostic and delivery-mode-agnostic** — the
  same shared policies and severity model apply in `local-code-review`
  and both modes of `github-pr-review`.
- **The canonical finding contract is shared; its rendering is a
  projection.** Both Skills render the one field-oriented shape in
  [`finding.md`](../shared/templates/finding.md); each surface projects
  the same fields.
- **Detail is presentation-only.** `include_finding_details` defaults to
  `true` locally and `false` on GitHub; it never changes the finding
  data, severity, or decision.
- **The final-summary voice is presentation-only.** `human_review_output`
  (default `false` for both Skills, natural-language-only — there is no
  CLI flag) selects a concise senior-engineer rendering of the final
  human-facing summary. Its derived companion `human_inline_findings`
  (default `explicit_value ?? human_review_output`) extends the same voice
  to `github-pr-review`'s inline review comments — a severity-keeping
  heading plus prose in place of the `Evidence` / `Impact` / `Fix` block.
  Mode on and mode off produce identical findings, severities,
  deduplication, verdict, GitHub review state, finding identity, canonical
  fix/action anchors and the `#164` / `#165` body fallback,
  machine-readable status, and publication order — only the wording of the
  summary (and, under `human_inline_findings`, the inline comments)
  changes.
- **Publication ordering is fixed for `github-pr-review`.**
  `final review comment == last publication event`: the one batched
  review submission (body + inline comments + event) carries the final
  human-facing summary and is the last review-owned publication; any
  optional machine-readable review status is published **before** it;
  nothing review-owned is published or edited afterward
  ([`review-output.md`](../skills/github-pr-review/policies/review-output.md),
  "Submission ordering").
- **Analysis, submission capability, and mutation authority are three
  separate things.** A clean or blocking result stays valid even when the
  account cannot submit the formal review; authorship never blocks
  analysis but forbids a formal self-review event; and for an external
  review, submitting `APPROVE` / `REQUEST_CHANGES` requires
  `explicitly-authorized auto-action` mode under trusted, scoped
  authorization and genuine reviewer independence
  ([`review-action-authorization.md`](../skills/github-pr-review/policies/review-action-authorization.md)).
  This gate composes with — never replaces — HEAD revalidation,
  stale-review protection, reviewer ownership, delta re-review, and the
  mechanical severity → decision derivation.
- **The optional machine-readable review status** is derived from the same
  canonical verdict, never a second engine; a blocking status is
  blocking-only enforcement allowed even for a self-review, a `success`
  status needs the same positive authorization as `APPROVE`, and a new
  HEAD inherits no green
  ([`review-status-enforcement.md`](../skills/github-pr-review/policies/review-status-enforcement.md)).
- **Git/GitHub state inspection is read-only** and never assumes GitHub is
  authoritative when local state diverges.
- **GitHub delivery** is the only stage permitted to mutate PR state, and
  only `github-pr-review` in active mode.
- **Orchestration ownership** belongs to the calling workflow (§4);
  **implementation ownership** always belongs to the implementing Agent
  or developer, never to either Skill.

## 10. Portable Core, Optional Runtime Adapters

The portable core is `SKILL.md` plus the canonical package-relative
policies, runbooks, templates, shared resources, and portable package
metadata. It owns all normative review semantics and expresses external
dependencies as capabilities, not vendor-specific tools.

Runtime adapters are subordinate optional resources — they may improve
discovery, presentation, or configuration, but cannot redefine review
scope, severity, mutation boundaries, output contracts, or dependency
requirements. Ignoring or removing an adapter leaves a coherent Skill.
Installation location (`.agents/skills/<name>/`, `.claude/skills/<name>/`,
`.cursor/skills/<name>/`, `.opencode/skills/<name>/`, …) is a consumer
concern; each archive keeps `SKILL.md` at its own root.

### Documentation-backed compatibility matrix

Format conclusions from current product documentation — not a claim that
every runtime loaded these packages during validation.

| Concern | Claude | Codex | Cursor | OpenCode |
|---|---|---|---|---|
| Canonical directory-based `SKILL.md` | documented | documented/static validation | documented | documented |
| Canonical `name` / `description` | documented | documented/static validation | documented | documented |
| Package-relative supporting files | documented | documented/static validation | documented | documented |
| Runtime-specific adapter required | no | no | no | no |
| Optional adapter used here | none | `agents/openai.yaml` | none | none |

The common canonical frontmatter deliberately contains only `name` and
`description`; keeping capability requirements in the Skill body avoids
coupling canonical validity to optional-field handling.
