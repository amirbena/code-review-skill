# Capability Architecture — Model and Recommendation

Research record. **Not a contract change**, not an implementation, and not
a rewrite proposal. Every conclusion below is derived from the repository
at commit `14650f9` (254 commits of history, `main` synchronized).

Measurements are reproducible: word counts are `wc -w` over the named
files; the link graph is extracted from markdown relative links under
`shared/` and `skills/`; co-change counts are `git log --name-only` over
full history with `chore(release)` bot commits excluded.

---

## 0. Executive summary

The repository is **not** a code monolith. There is no review engine to
split: `scripts/` is developer tooling (packaging, release, governance,
benchmark harness, sandbox, metadata validation), and the review "runtime"
is a model reading Markdown. The monolith is therefore an
**instruction-loading monolith**, and the architectural unit that matters
is *the set of files a review must read before it can produce its first
finding*.

Three measured facts frame everything:

1. **A `github-pr-review` invocation that follows its own canonical index
   to completion reaches ~81,300 words (~108,000 tokens) of instruction**
   — `skills/github-pr-review/` (41,834 words, README excluded) + the 17
   shared policies its `SKILL.md` §2 mandates (25,227) + the three shared
   templates (14,258). Following one more link hop from
   `review-scope.md` reaches the rest of `shared/` (65,486 words total),
   for a worst case near 110,000 words.
2. **The `shared/` link graph has 214 edges over 38 nodes and a single
   strongly-connected component of 35 of them.** Only
   `file-reviewability.md` and `review-ownership.md` (pure sinks) and
   `verdict-consistency.md` (in-degree 0) sit outside it. There is no
   topological order for a reader to follow, and no subgraph that can be
   loaded without, textually, reaching everything else.
3. **Both distributed archives ship the identical shared tree** — all 35
   shared policies and all 3 shared templates.
   `scripts/packaging/package-manifest.json` has one flat `shared_files`
   list applied to both skills, so `local-code-review-skill.zip` ships
   `mutation-authority.md`, `agent-delegation.md`, `parallel-review.md`,
   `trusted-host-execution.md` and all four deepening policies — none of
   which its `SKILL.md` mandates. Packaging has no notion of a per-skill
   or per-capability shared subset.

The recommendation is a **modular monorepo (Model A) with an explicit,
generated capability manifest** — not a repository split. Over 188
non-bot commits, `shared/policies/` and `skills/github-pr-review/`
co-change in 73%/66% of each other's commits, `shared/policies/` has
**never once** changed alone in 59 commits, and 71% of all skill/shared
commits also touch `tests/`. Separate repositories would convert
same-commit edits into cross-repo version negotiation and buy nothing,
because the latency problem is caused by *load scope*, not *repository
count*.

The decisive finding is that **the obstacle is not the capabilities —
it is two hand-maintained registration files.** The six domain-deepening
policies have **zero co-change with each other** after birth: each was
added in its own PR, touching only its own policy, its own test, and two
registration points. Those two points are
`shared/policies/review-scope.md` (25 changes; reaches both Skills'
runbooks, the policy index, and the comparison doc roughly every other
commit) and `scripts/packaging/package-manifest.json` (21 changes via
`--follow`, 86% of them alongside `shared/policies/`). **Every capability
addition edits both, by hand.**

So the first step is not to extract a capability. It is to **make
registration declarative and generated**, reconciling the three divergent
dependency declarations that already exist (§A.9) into one manifest. The
first capability to ride that manifest is **specialist-depth** —
`specialist-depth.md` plus the four `*-deepening.md` policies, ~8,977
words that are never named by either `SKILL.md`, already carry an explicit
activation and composition contract, and already have five dedicated
benchmark corpora.

---

## A. Current-state diagnosis

### A.1 What "monolithic" actually means here

`AGENTS.md` already states the correct principle — *"File size is a review
trigger, not a limit"* — and
[`../large-file-decomposition.md`](../large-file-decomposition.md) already
worked the file-size seams. This record is about a different axis: not how
big a file is, but **how much must be read before useful work begins.**

The relevant boundary is the one an agent crosses when it opens a file it
did not need. Today that boundary does not exist anywhere in the
repository — not in `SKILL.md`, not in the packaging manifest, not in the
link structure.

### A.2 Evidence 1 — the always-loaded surface is nearly the whole system

Both `SKILL.md` files carry a **"Required Policy Loading"** section that
mandates a fixed batch. For `github-pr-review` that batch is 17 shared
policies:

| Policy | Words |
| --- | ---: |
| `review-scope.md` | 4,656 |
| `runtime-validation.md` | 2,811 |
| `review-context.md` | 2,327 |
| `large-pr-partitioning.md` | 1,987 |
| `invocation-options.md` | 1,936 |
| `change-risk-signals.md` | 1,664 |
| `review-evidence.md` | 1,658 |
| `review-stopping-criteria.md` | 1,455 |
| `repository-expansion.md` | 1,313 |
| `repository-instructions.md` | 1,164 |
| `requirement-coverage.md` | 1,015 |
| `evidence.md` | 892 |
| `severity.md` | 841 |
| `file-reviewability.md` | 525 |
| `remediation-guidance.md` | 465 |
| `review-ownership.md` | 327 |
| `git-safety.md` | 191 |
| **subtotal** | **25,227** |

Plus `shared/templates/` (`finding.md` 7,250 + `finding-rendering.md`
4,356 + `review-summary.md` 2,652 = 14,258) and the Skill's own packaged
tree (41,834). **81,319 words before the first line of the diff is read.**

Several of these are mandated unconditionally while being *self-declared
conditional*. `large-pr-partitioning.md` states it activates only above a
fixed diff-size threshold. `requirement-coverage.md` states it activates
only when authoritative requirements are supplied.
`file-reviewability.md` applies only when a changed file is classifiable
into one of its categories. `runtime-validation.md` resolves to
`unavailable` without a declared command. Each is loaded every time
anyway, because `SKILL.md` §2 is a flat list with no activation
predicate attached to an entry.

### A.3 Evidence 2 — the link graph is one cycle

The `shared/` graph (38 linked nodes, 214 edges) has a **single 35-node
SCC**. Centrality is concentrated in four files:

| File | In-degree | Out-degree |
| --- | ---: | ---: |
| `severity.md` | 26 | 4 |
| `review-scope.md` | 25 | **18** |
| `evidence.md` | 23 | 8 |
| `templates/finding.md` | 15 | 13 |

`review-scope.md` is simultaneously the most-depended-upon and the
most-depending file in the layer. That is the single clearest structural
smell: it is both a foundation (what is examined, the dimension taxonomy)
and a router (14 `…owned by <other policy>` hand-offs dispatching into
every sub-domain and specialist). Its own text concedes the dual role —
*"The taxonomy below is a routing and reasoning aid."*

The practical consequence for loading: because `review-scope.md` is
always loaded and links to all four deepening policies,
`architectural-placement.md`, `api-contract-compatibility.md`,
`null-absence-risk.md`, `failure-retry-recovery.md`,
`affected-test-analysis.md`, `root-cause-consolidation.md` and
`specialist-depth.md`, *every* conditional pass in the repository sits one
hop from the mandatory set. An agent that chases links — which is exactly
what "read the canonical owner" instructs it to do — loads all of it.

### A.4 Evidence 3 — nine policies are reachable only transitively

Nine shared policies are **never named by any file under `skills/`**:
`api-contract-compatibility.md`, `architectural-placement.md`,
`database-migration-deepening.md`, `distributed-systems-deepening.md`,
`failure-retry-recovery.md`, `jira-context.md`, `null-absence-risk.md`,
`performance-deepening.md`, `security-deepening.md` — roughly 13,000
words reachable only by chasing links out of `review-scope.md`,
`specialist-depth.md`, or `review-context.md`.

This is the worst of both worlds. The material is not reliably loaded
(an agent that reads only the mandated batch never opens it), and it is
not reliably *not* loaded (an agent that follows canonical-owner links
opens all of it). Load behavior is undefined, which means both recall and
token cost are undefined.

`jira-context.md` is a clean instance of the pattern: both `SKILL.md`
files invoke it *by section name* — "`review-context.md`'s 'Jira context
resolution'" — rather than by filename, even though issue #198 moved the
full procedure into its own file. That reference still resolves —
`review-context.md` keeps a short "## Jira context resolution" section
that correctly points onward to `jira-context.md`'s "full procedure" — so
this is a deliberate thin-pointer layer, not a broken link. What it shows
is narrower but still real: the file a reader actually needs
(`jira-context.md`, 955 words) is never named directly by either
`SKILL.md`, so a load strategy keyed on `SKILL.md`'s literal filenames
misses it entirely, even though the section-name reference correctly
resolves for a human reader following links by hand.

### A.5 Evidence 4 — policies are carrying orchestration

Of 35 shared policies, **19 carry some execution/ordering responsibility
and 8 are orchestrators in substance**, named "policy" only by directory
convention:

| File | Orchestration it owns |
| --- | --- |
| `review-stopping-criteria.md` | Decides **which passes must have executed** before a review may terminate; enumerates required sub-passes per depth level; owns the closed set of incomplete triggers. This is a must-execute/eligibility engine. |
| `verdict-consistency.md` | *"The comparator runs at exactly four points"*, each named as a specific runbook step in both Skills. A pipeline gate, not an invariant. |
| `review-scope.md` | The dimension/sub-domain dispatch table (18 out-edges, 14 hand-offs). |
| `change-risk-signals.md` | *"The depth level is derived by this exact, reproducible ordering"*, steps 1–7; its output drives expansion ceilings, partitioning, and stopping criteria. |
| `large-pr-partitioning.md` | *"build partitions by this exact, reproducible ordering"*, steps 1–5; per-unit review and cross-unit aggregation. |
| `parallel-review.md` | *"## Execution-policy decision — Select parallel review only when both gates pass"*, with a decision tree. |
| `runtime-validation.md` | Phase placement: *"after target-repository instruction discovery and before findings are finalized … it never runs after the decision is derived."* |
| `agent-delegation.md` | Spawn topology and tree-wide budgets, gated on `parallel-review.md`'s execution decision. |

`skills/github-pr-review/policies/github-review.md` is the same pattern at
the Skill level and is more explicit about it: it sequences 16 sub-policies
and states *"This order is the authoritative dependency order: a later
file's rules assume every earlier file's gates have already resolved for
this invocation."* That is an orchestrator, described in its own
`SKILL.md` as *"the canonical index."*

The diagnosis is not that these documents are wrong. They are correct and
well-tested. The diagnosis is that **orchestration is spread across ~19
files that each also carry semantics**, so there is no single place that
can decide what to load, and no file that can be skipped without risking
the loss of an ordering rule embedded in it.

### A.6 Evidence 5 — packaging has no capability boundary

`scripts/packaging/package-manifest.json` declares one flat `shared_files`
array (39 entries) copied into **both** archives. Consequences:

- `local-code-review-skill.zip` ships GitHub-mutation and worker-spawn
  policy (`mutation-authority.md`, `agent-delegation.md`,
  `parallel-review.md`) that its `SKILL.md` explicitly describes as
  absent — *"This Skill holds no `spawn_agent` capability of its own."*
- Adding any shared policy requires editing the manifest. Over full
  history `shared/policies/README.md` and `package-manifest.json`
  co-change heavily; the manifest is a central registry that every
  capability addition must touch.
- There is no declaration anywhere — manifest, metadata, or `SKILL.md` —
  that says *this policy belongs to this capability and loads under this
  condition*. The information needed for lazy loading does not exist in
  machine-readable form.

### A.7 Evidence 6 — measurement is coupled to rendering internals

The benchmark subsystem is strategically important and largely sound, but
it has three structural facts that any decomposition must respect:

- **The production path exercises 4 of ~180 cases.**
  `runtime_platform/benchmark/scripts/run_benchmark.py` and the reference runner both use a
  **non-recursive** `corpus_dir.glob("*.yaml")`, so only the four
  root-level corpus cases ever run. The 22 sub-corpora are validated
  statically (schema, ids, anchors, README links) but never reviewed.
- **The Skill-under-test binding is unverified.**
  `benchmark_review_adapter.py` passes `--plugin-dir` as a documented
  best-effort hint; `skills/` is a packaging source tree, not a plugin
  directory, so a run may score an ambiently installed Skill rather than
  the checkout's.
- **The adapter spans the most boundaries of any asset in the
  repository.** It imports the test tree from production code
  (`from runtime_platform.benchmark.reference.benchmark_runner import ProducedFinding`),
  hardcodes the P0/P1/P2 vocabulary, encodes `finding-rendering.md`'s
  exact heading/location/result shapes as regexes, and its prompt asserts
  its own approval to satisfy `local-code-review`'s invocation-approval
  policy. Any rendering change silently breaks parsing.

Separately, `runtime_platform/benchmark/taxonomy.md`'s `affected_surface` dimension
(`runtime_platform/benchmark/reference/benchmark_taxonomy.py`) hardcodes a path
prefix allowlist (`shared/`, `skills/`, `docs/benchmark/`,
`runtime_platform/benchmark/reference/`, plus the runtime-adapter exact files) that
is pinned by prose in that doc. (This section originally described
`scripts/benchmark/benchmark_ci_classifier.py`'s equivalent allowlist (at
that file's pre-#457 location), pinned by `docs/benchmark/ci-integration.md`; that CI workflow and
classifier were retired by
[#420](https://github.com/amirbena/code-review-skill/issues/420), and
the taxonomy's own allowlist is the analogous hardcoded surface today.)
**Any path move in a capability refactor silently changes PR-time
classification unless the taxonomy is updated in the same change.**

### A.8 What is *not* wrong

Stating this explicitly, because the task is to find seams and not to
rewrite:

- The **shared review standard** is correct and is the repository's main
  asset. One severity model, one evidence bar, one finding contract,
  consumed identically by both Skills. Nothing below proposes forking it.
- The **capability model already exists** in
  `shared/policies/specialist-depth.md`: evidence-driven activation,
  0..N composability, capability provenance on findings, cascading bounded
  by `repository-expansion.md`. The repository invented the right
  abstraction and then did not apply it to loading.
- The **trust architecture** (`docs/threat-model/`, 70 catalog scenarios)
  is explicitly designed to hold against a non-cooperative reviewer. It
  constrains the loading design in a way §C.4 treats as a hard rule.
- The **measurement architecture** (`docs/benchmark-measurement-architecture/`)
  already fixes nine layers, single owners, and the boundary
  *telemetry ≠ benchmark ground truth ≠ analytics ≠ learning*, plus the
  invariant "no duplicate reviewer/runner/evaluator implementations".
  This record inherits all of it rather than re-deciding any of it.

### A.9 Evidence 7 — three inconsistent declarations of the same dependency set

There are already three machine- or human-readable statements of "what
this Skill needs," and **no two agree**:

| Surface | Declares | Count |
| --- | --- | ---: |
| `SKILL.md` §2 "Required Policy Loading" | prose batch, no activation predicate | 17 (github) / 18 (local) shared policies |
| `metadata/skill.yaml` `shared:` | machine-readable list | 18 (local) / 19 (github) policies, **2** templates |
| `package-manifest.json` `shared_files` | flat list, identical for both archives | **35** policies, **3** templates |

Concretely: **17 shared policies ship inside `local-code-review-skill.zip`
that the Skill's own metadata does not declare** — including
`mutation-authority.md`, `agent-delegation.md`, `parallel-review.md`, all
four `*-deepening.md` files, `specialist-depth.md`,
`verdict-consistency.md`, and `architectural-placement.md`.

And `shared/templates/finding-rendering.md` — 4,356 words, the canonical
owner of every finding rendering and of the Senior voice contract — is
**declared in neither `metadata/skill.yaml`**, though the packaging
manifest ships it and both Skills' templates link to it.

This is the crux. The repository has three partial, divergent views of its
own dependency graph and no single authoritative one. **A capability
manifest is therefore not a new concept to introduce — it is the
reconciliation of three that already exist.**

### A.10 Evidence 8 — duplication has already produced live drift

Duplication in this repository is mostly well-controlled by the
"one canonical home per rule" invariant. Two places where it has already
failed are worth naming, because they are the cost of the current shape:

**`skills/local-code-review/policies/pr-context.md` vs
`shared/policies/review-evidence.md`.** The local file opens by
disclaiming exactly what it then restates — *"the still-relevant /
resolved / stale / duplicate / settled-decision / speculative-discussion
classification … are owned by `review-evidence.md` and are **not restated
here**"* — and then defines a **different** taxonomy:

| Concern | `shared/review-evidence.md` | `local/pr-context.md` |
| --- | --- | --- |
| Item classification | 6 categories (still-relevant / resolved / stale / duplicate / settled decision / speculative discussion) | **5** categories (actionable defect-finding / architectural-design decision / implementation preference-suggestion / informational comment / resolved-or-obsolete) |
| Reconciliation outcomes | 5 (still-relevant / resolved / stale-requires-re-evaluation / duplicate / materially-different) | **4** (still present / resolved / requires re-evaluation / outside the current local review scope) |
| Settled-decision bar | explicit conclusion, accepted/resolved thread, unambiguous direction, **or a direct maintainer statement** | explicit conclusion, accepted/resolved thread, unambiguous direction — *maintainer statement dropped* |

Lexical overlap is only ~6.5%, which is *worse* than a copy, not better:
the text was independently rewritten, so the two taxonomies drifted
silently and no link-checking or duplication test can see it.

**Presentation-option wiring is restated in six packaged files.** The
`human_review_output` / `human_inline_findings` guarantee ("never changes
findings, severity, dedup, verdict…") appears in
`shared/templates/review-summary.md`, `shared/templates/finding-rendering.md`,
`skills/github-pr-review/policies/review-output.md`,
`templates/external-review-summary.md`, `templates/inline-finding.md`, and
`skills/local-code-review/templates/local-review-report.md`, plus both
`SKILL.md` §1s and both `metadata/skill.yaml` files. It is the
most-repeated sentence in the repository.

**Two shared files reach down into one Skill.**
`shared/policies/review-evidence.md` contains a "GitHub PR review —
additional application" section, and `shared/templates/review-summary.md`
contains a "Human full rendering for body/fallback findings
(`github-pr-review` only)" section. Both are GitHub-specific content
inside files whose stated contract is Skill-neutrality.

### A.11 Evidence 9 — the two Skills already share thirteen consecutive phases

Comparing the three runbooks step by step
(`skills/local-code-review/runbooks/local-review.md`,
`skills/github-pr-review/runbooks/passive-pr-review.md`,
`skills/github-pr-review/runbooks/active-pr-review.md`):

- **Thirteen consecutive engine phases are identical across all three**,
  in the same order, with the same `a`/`b`/`c` sub-step decomposition and
  largely the same prose: repository-instruction discovery →
  runtime-validation resolution → parallel planning → change-risk depth →
  repository expansion → large-PR partitioning → the review pass →
  aggregation → severity + remediation-scope boundary → finalize →
  requirement coverage → stopping criteria → verdict consistency →
  compose body → render.
- The two PR runbooks share **51.7%** of the passive runbook's 6-grams.
- Some phases assert their own parity in triplicate: local step 8a says
  the trusted-host resolution "is the same resolution `github-pr-review`
  performs, never a per-Skill variant," and both PR runbooks say the same
  sentence about `local-code-review`. Three documents each asserting they
  match the other two is a contract that should be expressed once.

The genuinely divergent phases are exactly: target resolution,
authorization, delta retrieval, optional checkout, prior-evidence
transport, publication, and cleanup. **That is the adapter surface, and
it is small.** Everything else is engine written out three times.

---

## B. Proposed capability map

### B.1 The organizing rule

A capability is a unit of **loading**, not of filing. It earns its
boundary when it has (1) a coherent responsibility, (2) an activation
predicate that can be evaluated from cheap inputs, (3) an input/output
contract that does not require arbitrary repository access, and (4) its
own benchmark evidence.

Two hard constraints bound the design:

- **Fail-closed loading.** Not loading a capability must only ever be
  able to *withhold* behavior, never to *grant* it. This is required by
  `docs/threat-model/threat-model.md`'s stated design constraint that the
  model "must remain useful even if the reviewing model is fully
  non-cooperative." A safety boundary that can be bypassed by declining
  to load its file is not a boundary. §C.4 makes this concrete.
- **The router stays small.** The failure mode of this whole exercise is
  replacing one monolith with an orchestrator that becomes the next one.
  §C.3 sets the budget and the mechanism that holds it.

### B.2 Always-resident core (never lazy)

| Capability | Responsibility | Inputs | Outputs | Depends on | Local/GitHub | Lazy? | Benchmarkable? |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **`review-kernel`** | The P0/P1/P2 model, the mechanical severity→decision derivation, the evidence bar, and one-owner-per-scope. Current files: `severity.md`, `evidence.md`, `review-ownership.md`. ~2,060 words. | finalized finding set | one severity per finding; one decision | none | both | **No** — it *is* the decision | Yes — `corpus/candidate-finding-validation/`, root corpus, #350 |
| **`finding-contract`** | The finding's fields, quality and conciseness bar, and defect classification. The non-derivation half of `shared/templates/finding.md` (~5,655 of 7,250 words). | candidate observations | canonical finding records | `review-kernel` | both | **No** | Yes — `corpus/consolidation/`, `corpus/analogue-placement-pattern/` |
| **`capability-posture`** | The always-true denials: `READ_ONLY` by default, `spawn_agent` absent by default, structurally incapable of `APPLY_PATCH`/`COMMIT`/`PUSH`, publication non-mutating by default. The *prohibition* half of `mutation-authority.md`, `agent-delegation.md`, `review-action-authorization.md`. Target ≤800 words. | invocation | the default-deny posture | none | both | **No** — safety | Yes — `corpus/mutation-boundary/`, `corpus/delegation-spawn/` |
| **`review-context-core`** | The four concepts (review target / review context / repository context / existing review evidence) and the never-widen rule. The core of `shared/policies/review-context.md`. | invocation inputs | normalized context model | `finding-contract` | both | **No** | Yes — `tests/reference/review/context_evidence.py` |
| **`invocation-options`** | Deterministic normalization of presentation options *before* reasoning begins. | raw invocation | canonical option booleans | none | both | **No** — phase zero | Yes — `tests/unit/review/test_invocation_options.py` |
| **`repository-instructions`** | Discover and apply the target repo's `AGENTS.md`/`CLAUDE.md` hierarchy before evaluating changed files. | repo snapshot, changed paths | per-file instruction chain | none | both | **No** — runs before evaluation | Yes — `tests/reference/review/repository_instructions.py` |

**Always-resident total target: ~12,000 words**, against today's ~39,500
(the mandated 17 shared policies + three templates). The reduction comes
entirely from moving conditional material out, not from deleting rules.

### B.3 Routing layer (always loaded, deliberately tiny)

| Capability | Responsibility | Inputs | Outputs | Depends on | Local/GitHub | Lazy? | Benchmarkable? |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **`review-router`** | Classify the change into a depth level and an **activated capability set**; declare which capabilities must have reached their stop condition before the review may terminate. Absorbs the *routing* half of `review-scope.md`, `change-risk-signals.md`'s classification ordering, and `review-stopping-criteria.md`'s must-execute table. **Budget: ≤2,500 words.** | changed-file list, diff size, cheap signals | depth level; activated capability set; coverage obligation | `review-kernel` | both | **No** | **Yes** — `corpus/risk-depth/` (5 cases) + `corpus/specialist-depth-composition/` (7 cases) already benchmark exactly this |

The router owns **predicates and a manifest**, never procedures. It
answers "which capabilities are in play and what must finish"; every
"how" stays inside the capability. This is the mechanism that keeps it
from regrowing: a rule that describes *how* to do something is, by
definition, not router material.

Note that `corpus/risk-depth/` and `corpus/specialist-depth-composition/`
already exist and already test routing and eligibility in isolation.
**The router is the only proposed component that arrives with a ready
benchmark suite.**

### B.4 Lazy capabilities

| Capability | Responsibility | Inputs | Outputs | Depends on | Local/GitHub | Lazy? | Benchmarkable? | Words |
| --- | --- | --- | --- | --- | --- | --- | --- | ---: |
| **`specialist-depth`** | Domain deepening for an already-implicated dimension: security, performance, database/migration, distributed systems. Composition contract + four domain capabilities. | implicated dimension + its base evidence; repo context within the authorized ring | additional findings with `capability` provenance; applicability status | `review-kernel`, `finding-contract`, `scale` (for ring bounds) | both | **Yes** | **Yes** — 5 corpora, 34 cases | 8,977 |
| **`conditional-passes`** | The signal-triggered passes: null-like absence risk, API/contract compatibility, failure/retry/recovery, affected-test analysis, architectural placement, root-cause consolidation. | change set, base-pass evidence | additional/consolidated findings | `review-kernel`, `finding-contract` | both | **Yes** (per pass) | **Yes** — `null-absence-risk/`, `api-compatibility/`, `analogue-placement-pattern/`, `consolidation/` (20 cases) | ~6,900 |
| **`scale`** | Bounded ring expansion and large-change partitioning: how far a trigger is followed and how an oversized diff becomes coherent review units. | change set, depth level | expanded context set; partitions; expansion report | `review-router` | both | **Yes** (partitioning is already threshold-gated) | Yes — `corpus/risk-depth/`, `corpus/repository-intelligence/` | 3,300 |
| **`runtime-execution`** | Repository-declared validation commands and targeted reproduction, inside a verified isolation boundary; the trusted-host fallback and its provenance. | declared command or suspected finding; capability probe | validation outcome + execution provenance | `capability-posture` | both | **Yes** — resolves `unavailable` when absent | **Yes** — `corpus/sandbox-adversarial/` (26 integration tests), `corpus/trusted-host-nl-authorization/` (13 cases) | 4,862 |
| **`parallel-execution`** | The execution-policy decision, worker input/output shape, spawn budgets, and centralized aggregation. Includes the *grant* half of `agent-delegation.md`. | capability probe; independent dimensions | execution plan; aggregated candidate findings | `capability-posture`, `review-router` | both (wired to GitHub today) | **Yes** — sequential is always the fallback | **Yes** — `corpus/delegation-spawn/` (23 cases) | 2,819 |
| **`context-resolution`** | Turning references into normalized context: Jira resolution, requirement coverage, prior-review-evidence reconciliation. | Jira ref / requirements / prior findings | normalized context; per-requirement coverage | `review-context-core` | both | **Yes** — all three are input-gated and already self-declared conditional | Yes — `tests/reference/review/{jira_context,requirement_coverage,pr_review_evidence}.py` | ~3,600 |
| **`remediation`** | Advisory fix direction and the three-part remediation-scope-boundary reasoning. | finalized finding | `Fix` / `Follow-up` framing | `review-kernel` | both | **Yes** | Yes — `tests/reference/review/remediation_guidance.py` | 1,481 |
| **`finding-placement-derivation`** | The deterministic fix/action-location ranking. The `## Deriving the fix/action location` half of `finding.md` (1,595 words) plus GitHub inline anchoring. | candidate finding + call graph within the ring | canonical fix/action location | `finding-contract` | both (inline anchoring GitHub-only) | **Yes** — needed only at finding construction | **Yes** — `corpus/analogue-placement-pattern/`, issue #387 | ~2,850 |
| **`stateful-review`** | Delta re-review eligibility, prior finding/lifecycle reconciliation, stack topology and effective base. | prior reviewed SHA + prior findings; base topology | review mode; reconciled lifecycle states; effective base | `review-router`, `finding-contract` | **GitHub today**; the lifecycle half is environment-neutral | **Yes** — only when prior evidence exists | Partially — `tests/reference/review/{delta_re_review,stacked_pr_topology}.py`; no YAML corpus yet | 6,454 |
| **`reviewer-assist`** | The private Reviewer Brief: what changed, stated focus, manual-review focus, open questions — composed from the finalized result, never published. | finalized findings + verdict | private brief | `review-kernel` | **GitHub today; no environment reason for that** | **Yes** | **Yes** — `corpus/reviewer-brief/` (9 cases) | 2,045 |
| **`publication-github`** | Analysis/publication separation, batched review construction, submission ordering, inline vs. body placement. | finalized findings + verdict + mode | one GitHub review submission | `review-kernel`, `capability-posture` | **GitHub only** | **Yes** | **Yes** — `corpus/publication-mode/` (22 cases), `corpus/verdict-consistency/` (17 cases) | ~9,800 |
| **`authorization-github`** | Identity, self-review boundary, reviewer independence, publication-mode resolution, GitHub event permission, machine-readable status. | authenticated identity, PR author, mode request | publication mode; permitted event; withholding reason | `capability-posture` | **GitHub only** | **Yes** — but see §C.4: absent ⇒ `PASSIVE` | **Yes** — `corpus/publication-mode/`, `corpus/mutation-boundary/` | ~6,200 |
| **`repository-checkout`** | Isolated, read-only, detached checkout at the PR head; guaranteed guarded cleanup. | PR head SHA | workspace path or degradation | `capability-posture` | **GitHub only** | **Yes** | Yes — `tests/reference/review/pr_checkout.py` | 1,307 |

### B.5 Adapters

| Adapter | Owns | Words |
| --- | --- | ---: |
| **`local-adapter`** | Repository-state categories and their detection commands, the `@{u}` sync rule, the SHA-256 staged-delta fingerprint, the local report surface, and the per-invocation approval contract. Current: `repository-state.md`, `invocation-approval.md`, `local-review-report.md`. | ~5,900 |
| **`github-adapter`** | PR scope retrieval and pagination-to-exhaustion, the 3,000-file REST cap, truncated-patch handling, the four prior-evidence surfaces and thread `resolved` semantics, GitHub transport. Current: `pr-scope.md`, `github/review-evidence.md`. | ~1,500 |

### B.6 Reclassifications this map proposes

Four current placements do not survive the analysis:

1. **`github-pr-review/policies/review-reasoning.md` is not a policy.**
   All eleven of its sections delegate their durable invariant to
   `shared/`; the disclaiming sentence *"this PR-specific policy does not
   restate them"* (or an "owned by …" equivalent) recurs in nine of them.
   The two exceptions add only an execution-capability fallback for a
   reviewing engine with no native codebase-search tool — a
   how-to-execute detail, not new review semantics. `local-code-review`'s
   runbook invokes the same passes by naming the shared sections
   directly, with no intermediary — proving the intermediary is
   unnecessary. It becomes part of `review-router`'s capability manifest,
   not a file.

2. **`local-code-review/policies/invocation-approval.md` is skill-specific
   but not environment-specific.** It constrains the *caller*, and the
   same invariant applies to any read-only review Skill. It is a shared
   contract with a per-Skill opt-in, not local-adapter material. (This is
   a classification change only — the rule and its owner are unchanged.)

3. **`reviewer-brief` and `parallel-review` are capability gaps, not
   environment boundaries.** `local-code-review` produces no Reviewer
   Brief and has no parallel policy. Nothing about a local delta prevents
   either. Today the asymmetry is invisible because the capability is
   filed inside one Skill's directory; under a capability manifest it
   becomes a one-line, reviewable decision.

4. **`shared/policies/security-deepening.md` and the trust architecture
   are two different things and must not merge into one "security"
   capability.** The former is a *review dimension* (authorization
   placement, confused deputy, sanitization in the code under review) and
   is lazy-loadable. The latter (`mutation-authority.md`,
   `agent-delegation.md`, `trusted-host-execution.md`,
   `review-action-authorization.md`, the 70-scenario threat catalog) is
   the *reviewer's own* capability boundary and its always-on half must
   never be lazy. The core hypothesis's single `security` capability
   would have fused them.

### B.7 Link-uniformity and change-independence agree

Two independent measurements point at the same conclusion for the
deepening family:

- **Link structure:** the four `*-deepening.md` policies have
  **byte-identical out-edge sets** (`evidence`, `remediation-scope-boundary`,
  `repository-expansion`, `review-scope`, `review-stopping-criteria`,
  `severity`, `specialist-depth`, `templates/finding`), plus one
  cross-edge `performance → distributed-systems`.
- **Change history:** they have **zero co-change with each other** after
  their birth commits. Each was added in its own PR, and none has been
  touched alongside a sibling since.

Uniform contract shape plus independent evolution is the definition of a
plugin family. The only thing making them feel monolithic is that their
registration is hand-maintained in two files that everything else also
touches.

Caveat on evidence strength: n = 1–2 commits per deepening policy. The
signal that they *do not* co-change is real (six independent additions,
zero cross-touches); the signal about *how often* each changes is not —
they are write-once artifacts so far.

---

## C. Progressive loading design

### C.1 The load sequence

```text
invocation
   │
   ├─ [T0] always-resident core + router        ~14,500 words
   │       review-kernel · finding-contract · capability-posture
   │       review-context-core · invocation-options
   │       repository-instructions · review-router
   │
   ├─ classify: changed paths, diff size, supplied inputs, capability probes
   │       → depth level (standard | elevated | deep)
   │       → activated capability set
   │       → coverage obligation (which must reach a stop condition)
   │
   ├─ [T1] load only the activated capabilities
   │       each returns: findings + evidence + execution metadata
   │                     + applicability status
   │
   ├─ aggregate → deduplicate → reconcile → severity → decision
   │
   └─ [T2] load the delivery capability for this adapter only
           local: report rendering
           github: authorization-github → publication-github
```

### C.2 What loads when — worked scenarios

Word counts are today's files grouped by the proposed capability, so they
are an upper bound on the target (extraction also removes restated prose).

| Scenario | Loaded beyond core+router | Approx. words | vs. today's ~81,300 |
| --- | --- | ---: | --- |
| **Ordinary correctness review**, small diff, no supplied context, no declared command | `remediation` | ~16,000 | loads ~20% |
| **Security-sensitive change** (auth path implicated) | `specialist-depth`/security only, `conditional-passes`/placement, `remediation` | ~21,000 | ~26% |
| **Architectural-placement analysis** | `conditional-passes`/placement + `finding-placement-derivation` + `scale` | ~22,000 | ~27% |
| **Sandbox / runtime-validation change** | `runtime-execution` + `specialist-depth`/security | ~21,000 | ~26% |
| **Mutation / delegation change** | `capability-posture` (already resident) + `parallel-execution` grant half | ~17,500 | ~22% |
| **Reviewer-assist / TL;DR only** | `reviewer-assist` | ~16,500 | ~20% |
| **GitHub publication** (active mode) | above + `authorization-github` + `publication-github` | ~32,000 | ~39% |
| **Large stacked PR re-review, deep, active** | nearly everything | ~78,000 | ~96% — the worst case is unchanged, as it should be |
| **Benchmark execution** | harness only; **no review instruction at all** | 0 | the corpus never loads the Skill's policy tree |

The shape to notice: **the expensive reviews stay expensive.** Nothing
here makes a deep, stacked, active PR review cheaper — it genuinely needs
that material. What changes is that the *common* case stops paying for the
*rare* one. Today every review pays the worst case.

### C.3 Keeping the router from becoming the next monolith

The stated risk is real, and this repository has already demonstrated it:
`shared/policies/review-scope.md` was explicitly decomposed by issue #288
("Decompose review-scope.md into cohesive owner policies") and **still
changed three more times afterward and still has out-degree 18.**
Decomposition alone did not retire the hub, because the hub's *routing
role* was never moved — only its content.

Four mechanisms, in order of force:

1. **A word budget with a test.** `review-router` ≤2,500 words, asserted
   by a `tests/policy/` check in the same style as the existing
   doc-conformance tests. A budget nobody measures is a wish.
2. **A structural rule: predicates, not procedures.** The router may
   state *which* capability activates under *what* condition and *what
   must have finished*. The moment it says *how*, the text belongs in a
   capability. This is mechanically checkable in the weak form (no
   numbered "reason in this order" blocks in the router).
3. **Generated, not authored, registration.** The capability list is
   derived from per-capability manifest front-matter, not hand-written in
   the router. Adding a capability then edits exactly one file — its own —
   which is the specific failure the co-change data identifies.
4. **No transitive links out of the router** except to capability
   manifests. The router must not link to a capability's *body*, or the
   one-hop-reaches-everything problem returns in a new location.

### C.4 Lazy loading must be fail-closed — the safety constraint

This is the sharpest design constraint and it comes from
`docs/threat-model/threat-model.md`'s own premise: the model "must remain
useful even if the reviewing model is fully non-cooperative," and every
rule must be "phrased in terms of a capability the runtime does or does
not grant" rather than "the model should not…".

If a safety boundary lives in a lazily-loaded file, **declining to load
it becomes a bypass.** A non-cooperative or prompt-injected reviewer would
simply not load `mutation-authority.md` and proceed.

The resolution is to split every capability-boundary policy along the
grant/deny line:

```text
DENY half  → always resident, tiny, unconditional
             "READ_ONLY by default"
             "spawn_agent absent by default"
             "structurally incapable of APPLY_PATCH / COMMIT / PUSH"
             "publication mode defaults to PASSIVE"

GRANT half → lazily loaded, only when a grant is actually sought
             the authorization procedure, the evidence bar,
             the single-use binding, the budgets
```

Under this split, failing to load the grant half can only ever result in
**no grant** — the default-deny posture already resident continues to
hold. Lazy loading can withhold capability; it can never confer it. This
matches the existing fail-closed convention throughout the repository
(`review-action-authorization.md`: "Ambiguity fails closed to `PASSIVE`";
`runtime-validation.md`: no verified isolation ⇒ `unavailable`;
`stacked-pr-review.md`: ambiguous topology ⇒ the *wider* scope).

Three capability-boundary policies need this split:
`mutation-authority.md`, `agent-delegation.md`, and
`review-action-authorization.md`. The always-resident deny half is
targeted at ≤800 words combined.

Two further rules follow:

- **The router may never be the thing that decides a safety boundary is
  inapplicable.** It routes analysis capabilities. Capability-boundary
  posture is resident and not routable.
- **`verdict-consistency.md` stays resident.** It is the comparator that
  catches a rendered decision disagreeing with the derived one — precisely
  the check that must survive a reviewer that has gone wrong. It is small
  (1,081 words) and its in-degree is already 0, so residency costs
  nothing structurally.

### C.5 What must always load — the answer

| Always resident | Why it cannot be lazy |
| --- | --- |
| `review-kernel` (severity, evidence, ownership) | It *is* the decision; there is no review without it |
| `finding-contract` (fields, quality bar) | Every capability's output conforms to it |
| `capability-posture` (deny halves) | Safety: not loading must never grant (§C.4) |
| `verdict-consistency` | Catches a reviewer whose render disagrees with its derivation |
| `review-context-core` (four concepts, never-widen) | Defines the target every capability is bounded by |
| `invocation-options` | Must normalize before reasoning begins |
| `repository-instructions` | Must run before any changed file is evaluated |
| `review-router` | Decides everything else |

Everything else in §B.4 is lazy.

---

## D. The local / GitHub relationship

### D.1 Finding: both should be thin adapters — the evidence is unusually direct

The core hypothesis asked whether `github-pr-review` should be treated as
the platform root. It should not, and neither should `local-code-review`.
Three measurements settle it:

1. **Thirteen consecutive engine phases are already identical across all
   three runbooks** (§A.11), in the same order, with the same sub-step
   decomposition and largely the same prose. The two PR runbooks share
   51.7% of the passive runbook's 6-grams.
2. **The parity is asserted in triplicate.** Local step 8a says the
   trusted-host resolution "is the same resolution `github-pr-review`
   performs, never a per-Skill variant"; both PR runbooks say the same
   about `local-code-review`. Three documents each claiming to match the
   other two is a contract expressed in the wrong place.
3. **`github-pr-review/policies/review-reasoning.md` has essentially no
   content of its own.** All eleven sections delegate their durable
   invariant to `shared/`, nine of them with the explicit disclaimer
   *"this PR-specific policy does not restate them"*; the other two add
   only an execution-capability fallback, not new review semantics.
   `local-code-review`'s runbook invokes the same passes by naming the
   shared sections directly, with no
   intermediary — proving the intermediary is unnecessary.

### D.2 What is genuinely shared

All of it, except transport and delivery. Specifically, everything the
task listed should be shared, is already shared or should be:

| Concern | Status today | Target |
| --- | --- | --- |
| Finding discovery | shared (`review-scope.md`) | shared capability |
| Severity | shared (`severity.md`) | `review-kernel`, resident |
| Evidence | shared (`evidence.md`) | `review-kernel`, resident |
| Placement (fix/action location) | shared (`finding.md`), **but inline anchoring is GitHub-only** | `finding-placement-derivation` shared; anchoring in `github-adapter` |
| Semantic-risk analysis | shared | `specialist-depth` + `conditional-passes` |
| Architecture analysis | shared (`architectural-placement.md`) | `conditional-passes` |
| Security analysis (of the code) | shared (`security-deepening.md`) | `specialist-depth` |
| Aggregation | shared in principle; written out three times in runbooks | one shared capability |
| Verdict derivation | shared (`severity.md`) | `review-kernel`, resident |
| **Finding identity** | **GitHub-only today** — buried in `pr-scope.md` | **shared** (see D.4) |
| **Finding lifecycle** | **GitHub-only today** — `stateful-delta-rereview.md` §3–§6 | **shared** (see D.4) |
| **Reviewer Brief** | **GitHub-only today** | **shared capability, both adapters** (see D.4) |

### D.3 What is genuinely environment-specific

The adapter surface is small and clean:

```text
local-adapter                       github-adapter
─────────────                       ──────────────
repository-state categories         PR metadata + pagination to exhaustion
  (committed/staged/unstaged/         (3,000-file REST cap, truncated
   untracked) + detection commands     patch media)
@{u} upstream sync resolution       stack topology + effective review base
SHA-256 staged-delta fingerprint    prior reviews / review comments /
local report surface                  issue comments / thread resolved state
per-invocation approval contract    isolated read-only checkout + cleanup
                                    identity, independence, event permission
                                    publication mode (PASSIVE|SEMI|ACTIVE)
                                    inline comment anchoring
                                    batched submission + ordering
                                    machine-readable status
```

These files survive an adapter refactor essentially whole:
`local/repository-state.md`; `github/review-authority.md`,
`pr-scope.md` (minus finding identity), `repository-checkout.md`,
`finding-placement.md`, `review-status-enforcement.md`,
`stacked-pr-review.md` §1–§4, `github/review-evidence.md`, and
`github/parallel-review.md`.

Note that `github/parallel-review.md` and `shared/parallel-review.md` are
the **model pair** for this whole exercise: 0.3% lexical overlap, the
shared file owning the contract and the skill file adding only PR-specific
placement and a runtime-capability table. Every other shared/skill pair
should look like that one.

### D.4 Three capability gaps disguised as environment boundaries

The co-change data shows `local-code-review` is a **follower, not a peer**:
over the recent 80 non-bot commits it changed alone **zero times**, 85% of
its commits also touched `shared/policies/`, and 92% also touched
`skills/github-pr-review/`. It is not an independent Skill today.

Three of its apparent "differences" have no environmental cause:

- **No Reviewer Brief.** A private "what changed / your stated focus /
  manual-review focus / open questions" handoff has nothing GitHub-specific
  in it. The only GitHub-specific rule is *"never published"* — a
  publication boundary, not a reason the brief cannot exist locally.
- **No parallel review.** The README concedes parallel execution "is
  currently wired into `github-pr-review`, not `local-code-review`."
  Nothing about a local delta prevents independent read-only workers.
- **No finding identity or lifecycle.** The deterministic finding-identity
  rule lives inside `github/pr-scope.md` (a *retrieval* file), and the
  lifecycle vocabulary (`DETECTED` / `STILL_PRESENT` / `RESOLVED` /
  `REOPENED` / `CONSOLIDATED` / `UNCERTAIN`) lives inside
  `stateful-delta-rereview.md`. Neither has GitHub content. Meanwhile
  `local-code-review` has its own parallel mechanism — the staged-delta
  fingerprint short-circuit — solving an adjacent problem differently.

Under a capability manifest each of these becomes a one-line, reviewable
decision (`reviewer-assist: local=yes|no`) instead of an invisible
consequence of which directory a file sits in. **That visibility is a
larger win than the token savings**, because it converts silent capability
drift into an explicit choice.

### D.5 The duplicated-engine risk is already realized, not hypothetical

The task asked to avoid duplicated review engines "unless there is strong
evidence duplication is necessary." There is no such evidence, and the
cost of the current duplication is already visible: §A.10 documents two
divergent taxonomies for prior-review-evidence classification (5 vs. 6
categories, 4 vs. 5 outcomes, a dropped "maintainer statement" clause) in
files that each disclaim restating the other.

---

## E. Repository topology

### E.1 Evaluating the three models

Assessed against the measured coupling, not against general principle.

#### Model A — modular monorepo

| Dimension | Assessment |
| --- | --- |
| Coupling | Matches reality. 71% of skill/shared commits touch `tests/`; `shared/policies/` has never changed alone in 59 commits. Same-commit edits stay same-commit. |
| Developer ergonomics | Unchanged and already good — one clone, one `python -m unittest discover`, one validator. |
| Cross-repo changes | None. The dominant change shape today (policy + registration + test + docs in one commit) needs no coordination. |
| Versioning | One version, as today. `scripts/release/` and its SemVer intent policy keep working unmodified. |
| Releases | Unchanged: two archives from one manifest. Capability granularity becomes a manifest concern, not a release concern. |
| CI complexity | Lowest. `validate.yml` keeps working. (`benchmark-check.yml`, referenced here when this record was written, was retired by #420; today's PR-time taxonomy's hardcoded prefix list needs one coordinated update per path move — see §K.) |
| Contributor workflow | Preserved, including the `(#issue) (#pr)` traceability convention and the contributor-owned issue classes. Capability boundaries make *more* work contributor-ownable, because a capability is a bounded blast radius. |
| Governance | `AGENTS.md` precedence and CODEOWNERS keep working; per-capability ownership becomes expressible. |
| Dependency management | No package manager needed — dependencies are markdown links plus a manifest. |
| Benchmark ownership | Corpus moves next to its capability, which the data supports: corpus↔policy commit overlap is 0 for 6 of 7 capabilities, so corpus already has an independent lifecycle. |
| Compatibility risks | Minimal. Archive contents are byte-comparable before and after each step. |
| Agent comprehension | **This is where the win is, and it is orthogonal to repository count.** An agent understands one capability by reading its manifest + body + corpus, not by reading `shared/`. |
| Token/context efficiency | Full benefit. Loading is governed by the manifest, not by directory layout. |
| Latency | Full benefit (§I). |

#### Model B — core repo + a small number of sub-repos

| Dimension | Assessment |
| --- | --- |
| Coupling | **Contradicted by the data.** A split of `review-core` / `review-security` / `review-benchmarks` would cut exactly where co-change is highest: `shared/policies/`↔`skills/` at 73%/66%, skill/shared↔`tests/` at 71% (rising to 91% in the recent window). |
| Cross-repo changes | Every capability addition today edits its policy, `review-scope.md`, `package-manifest.json`, and a test. In Model B that is a 3-repo choreography for a routine change. |
| Versioning | Introduces skew between a policy and the manifest that registers it — a class of bug that cannot exist today. |
| CI complexity | Multiplies. The benchmark CI classifier's path allowlist would have to reason across repositories. |
| Benchmark ownership | **Actively harmful.** A separate `review-benchmarks` repo would formalize the one boundary the measurement architecture explicitly warns about, and would strand `runtime_platform/benchmark/reference/*_fixtures.py` — corpus data for eight sub-corpora that lives in the test tree — on the wrong side of a repo line. |
| Agent comprehension | No better than Model A: an agent still needs the capability + its contract + its corpus, and now must fetch them from two places. |
| Token efficiency / latency | **No effect.** Load scope is set by the manifest, not by which repository a file sits in. |

Model B buys nothing the manifest does not already buy, and costs
coordination on the repository's most common change shape.

#### Model C — multiple capability repositories

Every Model B objection, amplified. With 13 proposed capabilities it would
produce 13 release cadences, 13 CI setups, and an N×N compatibility matrix
for a system whose entire "runtime" is markdown. The measurement
architecture's invariant — *"no duplicate reviewer/runner/evaluator
implementations"* — becomes materially harder to hold across 13
repositories than within one. **Rejected.**

#### The counter-case, stated fairly

The one genuine argument for splitting is independent capability
versioning: a consumer pinning `security-deepening@2` while tracking
`review-core@5`. Two things defeat it here. First, nothing consumes these
capabilities independently — distribution is two zip archives, and a
capability is meaningless without `review-kernel`. Second, a manifest with
per-capability version fields delivers the same pinning inside one
repository, without the coordination cost. If a genuine third-party
consumer of a single capability ever appears, that is the moment to
revisit — and the manifest is exactly what would make the split cheap
then. **Model A is not a permanent refusal to split; it is the structure
that makes a later split possible.**

### E.2 Recommended topology — one repository

```text
code-review-skill/                       (unchanged repository, restructured internals)
│
├── responsibility
│     Author, benchmark, govern and package the Code Review Agent Skills
│
├── capabilities/                        ← NEW: the unit of loading and ownership
│   │   Each capability directory is self-contained: manifest, body,
│   │   corpus, tests. Adding one touches this directory only.
│   │
│   ├── _kernel/                         always resident
│   │     capability.yaml · severity.md · evidence.md · review-ownership.md
│   │     finding-contract.md · capability-posture.md · verdict-consistency.md
│   │     review-context-core.md · invocation-options.md
│   │     repository-instructions.md
│   │     corpus/ · tests/
│   │
│   ├── _router/                         always resident, ≤2,500 words
│   │     capability.yaml · review-router.md
│   │     corpus/  ← from docs/benchmark/corpus/{risk-depth,
│   │                    specialist-depth-composition}/
│   │     tests/
│   │
│   ├── specialist-depth/                lazy
│   │     capability.yaml · specialist-depth.md
│   │     security-deepening.md · performance-deepening.md
│   │     database-migration-deepening.md
│   │     distributed-systems-deepening.md
│   │     corpus/  ← the five matching corpora, unchanged
│   │     tests/
│   │
│   ├── conditional-passes/              lazy
│   ├── scale/                           lazy
│   ├── runtime-execution/               lazy
│   ├── parallel-execution/              lazy
│   ├── context-resolution/              lazy
│   ├── remediation/                     lazy
│   ├── finding-placement/               lazy
│   ├── stateful-review/                 lazy
│   ├── reviewer-assist/                 lazy
│   ├── publication-github/              lazy, github only
│   └── authorization-github/            lazy, github only
│
├── adapters/                            ← the two Skills, now thin
│   ├── local-code-review/
│   │     SKILL.md · capability-set.yaml
│   │     repository-state.md · invocation-approval.md
│   │     runbooks/ (adapter phases only) · templates/
│   └── github-pr-review/
│         SKILL.md · capability-set.yaml
│         pr-scope.md · repository-checkout.md · review-evidence.md
│         runbooks/ (adapter phases only) · templates/
│
├── runtime_platform/                    ← measurement + tooling
│   ├── benchmark/   harness contracts, reference models, runner, adapter
│   ├── packaging/   manifest GENERATED from capability.yaml files
│   ├── release/ · governance/ · sandbox/ · skill_metadata/
│
├── docs/                                research records, features, threat model
├── policies/                            repository-development governance
└── AGENTS.md                            unchanged entrypoint
```

Dependencies: `adapters/* → capabilities/* → capabilities/_kernel`.
`runtime_platform/*` depends on capability manifests, never on capability
bodies. No capability depends on an adapter. No capability depends on
`docs/` or `policies/`, preserving the existing packaged-independence
invariant.

**This is a directory restructure, not a repository change.** It can be
approached one capability at a time, and at every intermediate point both
archives still build and are byte-comparable.

### E.2.1 Naming: `runtime_platform/`, not `platform/` (#458)

The topology above originally named this directory `platform/`. That
literal name collides with Python's standard-library `platform` module:
a package directory named `platform/` on the repository root (already on
`sys.path` for this repo's absolute imports, e.g.
`runtime_platform.benchmark.reference.*`) shadows the stdlib module for every
`import platform` executed afterward in the same interpreter — including
`scripts/sandbox/capability.py`'s use of `platform.system()` for sandbox
capability detection, a security-relevant subsystem
(`area:security-boundaries`). Once anything imports this repository's
`platform` package in a process (a near-certainty across a full `pytest`
run), `sys.modules` caching makes the collision apply regardless of
import order.

**Decision: rename the directory to `runtime_platform/`.** This removes
the hazard at the source rather than defending individual call sites
against it — a per-call-site guard (e.g. hardening
`scripts/sandbox/capability.py`'s import) only protects the one known
usage today and gives a future `import platform` anywhere else in the
repository no mechanical way to fail loudly. `runtime_platform` keeps the
directory's "measurement + tooling" meaning from §E.2, stays a valid
Python identifier (unlike hyphenated alternatives such as
`runtime-platform`, which cannot be imported as `runtime_platform.<sub>`
without extra machinery), and does not read as a private/internal name
the way a leading-underscore `_platform` would for a top-level,
publicly-relevant directory.

No code change is required in `scripts/sandbox/capability.py`: its plain
`import platform` continues to resolve to the stdlib module once this
repository's own package is no longer named `platform`.

This decision is scoped to the top-level directory name only; it does not
change §E.2's topology, ownership boundaries, or contents otherwise.
Downstream references to the old `platform/` name — every occurrence in
`benchmark-ownership-boundary-checkpoint.md` (§3, §4, §7 item 2, §8) and
in issue #457 — are updated to `runtime_platform/` accordingly.

---

## F. Dependency graphs

### F.1 Current state

```text
                      ┌──────────────────────────────────────┐
                      │  AGENTS.md → policies/  (repo-dev)   │
                      │  never referenced by packaged files ✓ │
                      └──────────────────────────────────────┘

  skills/local-code-review        skills/github-pr-review
        SKILL.md                        SKILL.md
           │                               │
           │                     policies/github-review.md
           │                     ◆ ORCHESTRATOR: 16 sub-policies
           │                       in "authoritative order"
           │                               │
           │                     review-reasoning.md
           │                     ◆ POINTER FILE: ~0 own content
           │                       (9× "does not restate them")
           │                               │
           └───────────────┬───────────────┘
                           ▼
              ╔════════════════════════════════════╗
              ║  shared/  — ONE 35-NODE SCC        ║
              ║  38 nodes · 214 edges              ║
              ║                                    ║
              ║   review-scope.md                  ║
              ║   ◆ in 25 / out 18 — HUB           ║
              ║   ◆ foundation AND router          ║
              ║      ├─▶ 4 × *-deepening           ║
              ║      ├─▶ specialist-depth          ║
              ║      ├─▶ architectural-placement   ║
              ║      ├─▶ null-absence-risk         ║
              ║      ├─▶ api-contract-compat       ║
              ║      ├─▶ failure-retry-recovery    ║
              ║      ├─▶ affected-test-analysis    ║
              ║      ├─▶ root-cause-consolidation  ║
              ║      ├─▶ change-risk-signals       ║
              ║      ├─▶ repository-expansion      ║
              ║      ├─▶ large-pr-partitioning     ║
              ║      ├─▶ review-stopping-criteria  ║
              ║      ├─▶ remediation-scope-boundary║
              ║      ├─▶ evidence ◀──┐  (2-cycle)  ║
              ║      └─▶ severity    │             ║
              ║                      │             ║
              ║   severity.md  in 26 ┘             ║
              ║   evidence.md  in 23               ║
              ║   templates/finding.md in 15/out 13║
              ║                                    ║
              ║   49 mutual 2-cycles               ║
              ║   ⇒ no topological reading order   ║
              ╚════════════════════════════════════╝
                           │
        ┌──────────────────┼──────────────────┐
        ▼                  ▼                  ▼
  verdict-consistency  file-reviewability  review-ownership
  in 0 (runbook-only)   sink               sink

  ── problems highlighted ──────────────────────────────────
  ◆ CIRCULAR: one 35-node SCC; 49 mutual pairs
  ◆ OVERLY CENTRAL: review-scope (both foundation and router),
       severity, evidence, templates/finding = 42% of all in-edges
  ◆ REACHING THROUGH BOUNDARIES:
       shared/review-evidence.md has a "GitHub PR review" section
       shared/review-summary.md has a "github-pr-review only" section
       github/pr-scope.md owns environment-neutral finding identity
  ◆ DUPLICATED ENGINE: 13 identical runbook phases × 3 documents;
       local/pr-context.md vs shared/review-evidence.md = 2 taxonomies
  ◆ PUBLICATION LEAKS INTO ANALYSIS:
       review-output.md owns ~100 lines of rendering contract
  ◆ RUNTIME/SECURITY LEAKS INTO GENERIC LOGIC:
       trusted-host-execution → invocation-options
       runtime-validation → templates/review-summary
  ◆ BENCHMARK COUPLED TO IMPLEMENTATION:
       benchmark_review_adapter.py encodes finding-rendering.md
       as regexes, hardcodes P0/P1/P2, imports tests/ from scripts/
  ◆ HAND-MAINTAINED REGISTRIES:
       review-scope.md (25 changes) + package-manifest.json (21)
       — every capability addition edits both
```

### F.2 Target state

```text
  adapters/local-code-review        adapters/github-pr-review
    SKILL.md + capability-set.yaml    SKILL.md + capability-set.yaml
    repository-state, approval,       pr-scope, checkout, evidence
    local report                      transport, GitHub runbook phases
          │                                     │
          └──────────────────┬──────────────────┘
                             ▼
                  ┌─────────────────────┐
                  │  capabilities/      │
                  │  _router/           │  ≤2,500 words, budget-tested
                  │  predicates only    │  links ONLY to manifests
                  └─────────┬───────────┘
                            │ activates a subset
      ┌──────────┬──────────┼──────────┬──────────┬──────────┐
      ▼          ▼          ▼          ▼          ▼          ▼
 specialist-  conditional-  scale   runtime-  parallel-  context-
   depth        passes              execution execution  resolution
      │          │          │          │          │          │
      ▼          ▼          ▼          ▼          ▼          ▼
 remediation  finding-   stateful-  reviewer-  publication-  authorization-
              placement    review     assist      github        github
      │          │          │          │          │          │
      └──────────┴──────────┴────┬─────┴──────────┴──────────┘
                                 ▼
                    ┌────────────────────────────┐
                    │  capabilities/_kernel/     │  ALWAYS RESIDENT
                    │  severity · evidence       │
                    │  ownership · finding       │
                    │  contract · context-core   │
                    │  invocation-options        │
                    │  repository-instructions   │
                    │  capability-posture (DENY) │
                    │  verdict-consistency       │
                    └────────────────────────────┘

                    runtime_platform/packaging/
                      reads capability.yaml → GENERATES the manifest
                      (never read by a capability)

  ── invariants this graph enforces ───────────────────────────
  ✓ ACYCLIC by construction: edges point only downward.
      Cross-capability reuse goes through _kernel, never sideways.
  ✓ NO HUB: _router holds predicates; _kernel holds contracts.
      Neither holds procedures, so neither attracts content.
  ✓ FAIL-CLOSED: the DENY half is resident; the GRANT half is lazy,
      so an unloaded capability can only withhold authority (§C.4).
  ✓ ONE REGISTRATION POINT: a capability declares itself in its own
      capability.yaml; router + manifest + metadata are generated.
  ✓ NO ADAPTER INBOUND EDGES: no capability may reference an adapter,
      which is what makes local/GitHub parity structural.
  ✓ BENCHMARK OWNED BY CAPABILITY: corpus travels with its capability;
      the harness depends on manifests, never on rendering internals.
```

---

## G. Capability contracts

### G.1 The shape

Deliberately minimal — the purpose is to prove each boundary is real and
can operate without arbitrary repository access, not to design a schema.
A formal schema is #67/#68's job, and these contracts are written so they
can become that schema's input rather than competing with it.

```yaml
capability: <name>
loads: always | on-activation
activation:            # omitted for always-resident
  - <predicate evaluable from the router's cheap inputs>
inputs:
  - <named, bounded>
outputs:
  - findings           # conforming to the kernel finding contract
  - evidence
  - execution metadata
  - applicability status   # engaged | not-applicable | unavailable(reason)
requires: [<other capabilities>]
never:
  - <what it may not do — the boundary's teeth>
benchmark: capabilities/<name>/corpus/
```

Every capability returns an **applicability status** even when it does
nothing. That is what lets the router satisfy the coverage obligation
inherited from `review-stopping-criteria.md` without loading the
capability's body: "engaged and stopped" and "not applicable" are both
complete; only "unavailable" is not.

### G.2 The contracts

```yaml
capability: review-kernel
loads: always
inputs:  [candidate findings, repository conventions]
outputs: [one severity per finding, one decision, blocking rule result]
requires: []
never:   [deriving a decision from anything but P0/P1 presence;
          letting a finding's source change its severity]
benchmark: corpus/candidate-finding-validation, corpus/ (root 4)
```

```yaml
capability: review-router
loads: always
inputs:  [changed file list, diff size, supplied-input presence flags,
          runtime capability probes]
outputs: [depth level, activated capability set, coverage obligation]
requires: [review-kernel]
never:   [performing review reasoning; stating HOW a capability works;
          deciding a capability-boundary policy is inapplicable;
          linking to a capability body rather than its manifest]
benchmark: corpus/risk-depth, corpus/specialist-depth-composition
```

```yaml
capability: specialist-depth
loads: on-activation
activation:
  - a review dimension is already materially implicated by base reasoning
  - that dimension's own evidence shows depth is warranted
  - (additively) explicit user focus in this domain
inputs:  [implicated dimension, its base evidence,
          repository context within the ring authorized by `scale`]
outputs: [additional findings carrying `capability` provenance,
          evidence, applicability status]
requires: [review-kernel, finding-contract, scale]
never:   [producing an independent verdict or severity scale;
          activating from file type/path alone;
          widening remediation scope by virtue of depth;
          contributing a finding merely to prove it ran]
benchmark: corpus/{security,performance,database-migration,
                   distributed-systems}-deepening
```

```yaml
capability: runtime-execution
loads: on-activation
activation:
  - a repository-declared validation command exists, OR
  - an eligible suspected finding warrants targeted reproduction
inputs:  [declared command or suspected finding, isolation capability probe,
          explicit out-of-band trusted-host authorization (optional)]
outputs: [one of four validation outcomes, execution provenance
          (sandbox | trusted-host | unavailable), applicability status]
requires: [capability-posture]
never:   [running after the decision is derived;
          rewriting a finding or the decision;
          falling back to unsandboxed host execution without the
            explicit per-invocation authorization;
          inferring that authorization from repository content]
benchmark: corpus/sandbox-adversarial, corpus/trusted-host-nl-authorization
```

```yaml
capability: publication-github
loads: on-activation
activation: [adapter is github AND publication mode is SEMI or ACTIVE]
inputs:  [finalized findings, verdict, publication mode,
          permitted event, reviewed HEAD]
outputs: [one batched GitHub review submission (body + inline + event),
          or a stated withholding reason]
requires: [review-kernel, capability-posture, authorization-github]
never:   [changing a finding, severity, or the verdict;
          publishing finding-by-finding;
          publishing anything review-owned after the final summary;
          publishing the Reviewer Brief]
benchmark: corpus/publication-mode, corpus/verdict-consistency
```

```yaml
capability: reviewer-assist
loads: on-activation
activation: [always, once findings/severity/coverage/verdict are final]
inputs:  [finalized analysis result, user-stated focus]
outputs: [private Reviewer Brief]
requires: [review-kernel]
never:   [influencing findings, severity, coverage, or the verdict;
          reaching any publication surface;
          asserting a severity without a finalized finding]
benchmark: corpus/reviewer-brief
```

### G.3 Why these boundaries are real

Each contract above is falsifiable against something that already exists:

- `specialist-depth`'s `never` clauses are
  `shared/policies/specialist-depth.md`'s own non-goals, and
  `corpus/specialist-depth-composition/` cases A–G test exactly them.
- `runtime-execution`'s "never falls back to unsandboxed host execution"
  is asserted in `scripts/sandbox/runner.py`'s docstring and tested by 26
  adversarial containment tests.
- `publication-github`'s ordering clause is
  `review-output.md`'s `final review comment == last publication event`,
  benchmarked by `corpus/publication-mode/`.
- `reviewer-assist`'s isolation clause is benchmarked by
  `corpus/reviewer-brief/`'s zero-GitHub-leakage assertions.

**No contract above invents a new rule.** Each names an existing
canonical rule and an existing test. That is the argument that these are
the repository's real boundaries rather than an imposed taxonomy.

---

## H. Benchmark architecture

### H.1 The corpus is already capability-shaped

This is the strongest structural asset in the repository, and the data
says it is ready:

- **The corpus directory names already match the capabilities.**
  `corpus/security-deepening/`, `corpus/performance-deepening/`,
  `corpus/distributed-systems-deepening/`,
  `corpus/database-migration-deepening/`, `corpus/null-absence-risk/`,
  `corpus/api-compatibility/`, `corpus/specialist-depth-composition/`.
- **Corpus and policy already have independent lifecycles.** Commit-set
  overlap between `corpus/<X>/` and `shared/policies/<X>.md` is **0 for 6
  of 7** capabilities. The established pipeline is *research record →
  capability → corpus in a later commit*. Moving a corpus next to its
  capability formalizes an independence that already exists.
- **Corpus is welded to `tests/`, not to `shared/`.** 31 of 31 corpus
  commits also touch `tests/`; only 26% touch `skills/`|`shared/`. So
  corpus and its tests must move **together** — which the proposed
  `capabilities/<name>/{corpus,tests}/` layout does by construction.

### H.2 The three benchmark tiers

| Tier | Owns | Assets today |
| --- | --- | --- |
| **Capability benchmarks** | Does one capability reason correctly in isolation? | `corpus/{security,performance,database-migration,distributed-systems}-deepening/`, `null-absence-risk/`, `api-compatibility/`, `analogue-placement-pattern/`, `consolidation/`, `candidate-finding-validation/`, `repository-intelligence/`, `semantic-implication/`, `dependency-supply-chain-deepening/` |
| **Orchestration benchmarks** | Does the router activate the right set, and is coverage honest? | `corpus/risk-depth/`, `corpus/specialist-depth-composition/`, `corpus/delegation-spawn/` |
| **Integration / E2E benchmarks** | Does an adapter deliver correctly end to end? | `corpus/publication-mode/`, `corpus/verdict-consistency/`, `corpus/reviewer-brief/`, `corpus/mutation-boundary/`, `corpus/sandbox-adversarial/`, `corpus/trusted-host-nl-authorization/`, `corpus/security-events/`, the root 4 |

### H.3 Assignment of every corpus asset

| Corpus | Cases | Boundary | Note |
| --- | ---: | --- | --- |
| root (4 YAML) | 4 | E2E | the **only** cases the production runner executes |
| `candidate-finding-validation/` | 11 | `review-kernel` | |
| `consolidation/` | 4 | `conditional-passes` | |
| `null-absence-risk/` | 6 | `conditional-passes` | |
| `api-compatibility/` | 6 | `conditional-passes` | |
| `analogue-placement-pattern/` | 4 | `finding-placement` | |
| `semantic-implication/` | 4 | `review-router` + `conditional-passes` | spans: it tests dimension activation |
| `security-deepening/` | 6 | `specialist-depth` | |
| `performance-deepening/` | 6 | `specialist-depth` | |
| `database-migration-deepening/` | 9 | `specialist-depth` | |
| `distributed-systems-deepening/` | 6 | `specialist-depth` | |
| `dependency-supply-chain-deepening/` | 6 | `specialist-depth` | no matching `shared/policies/` file — see §H.5 |
| `specialist-depth-composition/` | 7 | **`review-router`** | cases A–G test activation and composition |
| `risk-depth/` | 5 | **`review-router`** | |
| `repository-intelligence/` | 5 | `scale` | inside `repository-expansion`'s ring |
| `delegation-spawn/` | ~23 (Python) | `parallel-execution` + `capability-posture` | spans |
| `mutation-boundary/` | ~28 (Python) | `capability-posture` | spans runtime + publication |
| `sandbox-adversarial/` | 26 tests | `runtime-execution` | not fixtures — integration tests |
| `trusted-host-nl-authorization/` | ~13 (Python) | `runtime-execution` | spans security |
| `security-events/` | ~19 (Python) | `capability-posture` | spans telemetry (#182) |
| `publication-mode/` | ~22 (Python) | `publication-github` + `authorization-github` | |
| `verdict-consistency/` | ~17 (Python) | `review-kernel` (comparator) + `publication-github` | |
| `reviewer-brief/` | ~9 (Python) | `reviewer-assist` | spans publication isolation |

### H.4 Two structural problems to fix alongside, not after

**The production runner sees 4 of ~180 cases.** `run_benchmark.py` and the
reference runner both use a **non-recursive** `glob("*.yaml")`. Every
sub-corpus is validated statically (schema, ids, anchors, README links)
but never actually reviewed. Capability benchmarks are therefore *defined*
but not *executed*. Per-capability corpus directories make the fix natural
— the runner iterates capabilities rather than one flat directory — but
the fix is a real behavior change and belongs in its own issue, gated by
the existing runtime-execution-class rules (a contributor PR must never
require a provider credential).

**The benchmark adapter is coupled to rendering internals.**
`benchmark_review_adapter.py` imports the test tree from production code,
hardcodes `{"P0","P1","P2"}`, encodes `finding-rendering.md`'s heading,
location and result shapes as regexes, and its prompt asserts its own
approval to satisfy `local-code-review`'s invocation-approval policy. A
rendering change silently breaks parsing. This is exactly the
"benchmark dependencies on implementation details" the task asks about, and
`runtime_platform/benchmark/claim-correspondence-adequacy.md` already diagnosed its
downstream effect: `defect_kind` is never emitted, so claim matching falls
through to token overlap. The structural fix is the #67 machine-readable
output schema — the adapter should parse a declared contract, not scrape a
human rendering. **This record does not propose a second fix; it flags
that the capability split does not remove this coupling and must not be
credited with removing it.**

### H.5 Inherited boundaries this record does not reopen

`docs/benchmark-measurement-architecture/` is authoritative and unchanged:
the nine layers and their single owners (two of which — analytics #131
and learning #130 — are closed `not planned` as product-layer
capabilities), the execution-class split (automatic/repository-triggered
vs. maintainer-controlled), the DAG across #329–#339 and #182, the
telemetry ≠ benchmark ground truth boundary, and the cross-cutting
invariant **"no duplicate reviewer/runner/evaluator implementations."**
That last one is a direct constraint on this record:
per-capability corpora must **not** grow per-capability runners, matchers,
or metrics. One harness, many corpora.

One loose end worth an issue rather than a decision here:
`corpus/dependency-supply-chain-deepening/` (6 cases) has no matching
`shared/policies/` file — its model lives in
`docs/dependency-supply-chain/` and its rule in `review-scope.md`'s
"Dependency / supply-chain deepening review" section. Under a capability
manifest it either becomes the fifth `specialist-depth` domain or is
explicitly recorded as a router-level pass. Today it is neither.

---

## I. Performance measurement

### I.1 No percentages are claimed

The task says not to invent percentages, and none appear here. What can be
stated today are **absolute word counts of instruction surface** (§A.2,
§C.2), because those are directly measurable from the repository.
Everything about latency and tokens must be **measured**, and the honest
current position is that **the repository cannot measure review latency at
all today** — the benchmark runs 4 cases, only on demand, and CI reports
"runtime unavailable" on a bare runner.

Establishing the baseline is therefore the *first* performance task, not
a later validation step. A split whose benefit is unmeasurable is a split
that cannot be defended.

### I.2 The metric set

| Metric | Why | Where it comes from |
| --- | --- | --- |
| **Instruction tokens loaded before first analysis** | The most direct measure of the actual problem, and the only one measurable *statically*, before any runtime exists | static: resolve the capability manifest for a given change and sum |
| Number of capability modules loaded | Proves routing is selective rather than loading everything | router output |
| Median review latency | Product experience | runtime execution (#330 Class 2) |
| p95 review latency | Catches routing that collapses to "load everything" on hard changes | runtime execution |
| Time-to-first-useful-finding | Distinguishes "finished sooner" from "started sooner" | runtime execution |
| Total input token consumption | Cost | runtime execution |
| **Finding recall** | **The quality guard.** Must not drop | `missed-and-incorrect-findings.md` (#55) |
| **False-positive rate** | The other quality guard | #55 |
| Severity accuracy | Routing must not shift severity | `severity-accuracy.md` (#56) |
| Duplicate noise | Aggregation must not regress | `duplicate-noise.md` (#57) |
| Benchmark pass rate | Overall | `regression-report.md` (#53) |
| Verdict consistency | Decision integrity | `corpus/verdict-consistency/` |

Every quality metric above **already exists as a specified contract with
a reference implementation.** No new evaluator is needed — which is both
convenient and required by the no-duplicate-evaluator invariant.

### I.3 The normalized metric, with a guard

```text
validated useful findings per 1,000 input tokens
```

Adopt it, but **never alone**. It is trivially gamed by reviewing less:
a review that loads nothing and finds one easy bug scores superbly. Pair
it with a hard gate:

```text
Accept an efficiency gain only when, on the same corpus:
    recall               is not lower than baseline
    false-positive rate  is not higher than baseline
    severity accuracy    is not lower than baseline
    verdict consistency  is unchanged
Otherwise the change is a regression regardless of its token savings.
```

This is the operational form of the task's constraint "do not optimize
token usage at the expense of review quality," and it matches the existing
convention that benchmark metrics are reported alongside a regression
comparison without silently gating on one number.

### I.4 Where the improvement should actually come from

Named specifically, so each can be confirmed or refuted:

1. **Not loading self-declared-conditional policies when their condition
   is false.** `large-pr-partitioning` (1,987 words) below threshold;
   `requirement-coverage` (1,015) with no authoritative requirements;
   `runtime-validation` + `trusted-host-execution` (4,862) with no
   declared command; `context-resolution` (~3,600) with no supplied
   context. On a small, context-free correctness review that is ~11,500
   words that today load unconditionally.
2. **Not loading domain deepening when no domain is implicated.** 8,977
   words, transitively reachable from an always-loaded file today.
3. **Not loading GitHub publication and authorization for a local
   review** — ~16,000 words currently shipped into
   `local-code-review-skill.zip` and reachable from it.
4. **Not loading stateful/stacked re-review on a first review of a
   non-stacked PR** — 6,454 words.
5. **Removing restated prose** as capabilities absorb their canonical
   owners: the 13 triplicated runbook phases, the six copies of the
   presentation-option guarantee, `review-reasoning.md` in full, and
   ~120 lines of repo-development changelog (`## History (issue #314)`,
   `## Migration from the pre-#314 model`) currently packaged inside
   `review-action-authorization.md`.
6. **A smaller worst case is *not* claimed.** A deep, stacked, active
   review on a large PR will load nearly everything, and should. The
   claim is only that the common case stops paying for it.

### I.5 What would falsify the whole thesis

Stated deliberately, because a research record that cannot be wrong is not
research. The split should be abandoned or rethought if, after the first
extraction:

- recall drops on the capability's own corpus — routing is missing
  activations that the always-loaded arrangement caught implicitly;
- the router grows past its budget in the first two capability additions —
  the predicates are not actually cheap;
- measured latency does not improve once a runtime exists, because load
  time was never the bottleneck relative to reasoning time.

The third is the most plausible and the least examined. It is why §J puts
the measurement harness before the second extraction.

---

## J. Migration sequence

### J.1 Preservation constraints for every step

Adopted from [`../large-file-decomposition.md`](../large-file-decomposition.md),
which established this discipline for the file-size pass:

- No change to behavior or public contracts. The finding schema, script
  CLI surfaces, workflow triggers, and Skill discovery metadata stay
  byte-stable.
- **Archive contents are byte-comparable before and after each step**,
  until a step deliberately changes them — and that step changes *only*
  archive membership, nothing else, so a diff of the two archive listings
  is the entire review surface.
- Test semantics unchanged; doc-conformance tests still pass against
  moved sections.
- One step per pull request, with the existing validation gate
  (`python3 -m unittest discover -s tests -t .`, both metadata validators,
  both `package-skills` scripts, `git diff --check`).
- **The taxonomy's hand-maintained path prefixes
  (`runtime_platform/benchmark/taxonomy.md` §2.2/§2.4,
  `runtime_platform/benchmark/reference/benchmark_taxonomy.py`) are updated in the
  same commit as any path move.** (This section originally named the
  #255 `benchmark_ci_classifier.py` allowlist as the thing a path move
  could silently invalidate; that workflow and classifier were retired by
  #420 — the taxonomy's own prefix lists are the analogous hardcoded
  surface today.) A path move without updating them silently changes
  PR-time classification/selection.

### J.2 The best first extraction — and why it is not a capability

**Step 1 is the capability manifest, not a capability move.**

The instinct is to extract `specialist-depth` first. The co-change data
says that would be premature: the six deepening policies have zero
coupling to each other, so moving them proves nothing about coupling —
but **every one of them edits `review-scope.md` and
`package-manifest.json` on the way in.** Those two hand-maintained
registries are the actual constraint, and they will constrain every
subsequent step identically.

Step 1 is also uniquely safe: it is **purely additive and changes no
packaged byte.**

```text
Step 1 — Declarative capability manifest (additive, zero behavior change)
  · Add capabilities/<name>/capability.yaml for each proposed capability,
    describing files, activation predicate, requires, never-clauses,
    and benchmark location. No file moves.
  · GENERATE scripts/packaging/package-manifest.json from those files;
    assert the generated output is byte-identical to today's. That single
    assertion proves the manifest is complete and correct.
  · Reconcile the three divergent declarations (§A.9): SKILL.md §2,
    metadata/skill.yaml, and the packaging manifest all become
    projections of capability.yaml. This closes two live defects — the 17
    undeclared policies in the local archive, and the missing
    finding-rendering.md declaration.
  Risk: none to runtime. Rollback: delete the generator, keep the
    checked-in manifest.
  Proves: registration can be declarative; the dependency graph is
    expressible.
```

```text
Step 2 — Per-skill shared subsets (first behavior-visible change)
  · Let capability.yaml drive per-archive membership so
    local-code-review-skill.zip stops shipping the 17 policies its own
    metadata does not declare.
  · Review surface is exactly a diff of two archive listings.
  Risk: low, and detected by the existing packaging-runtime-boundary
    tests. Rollback: revert to the flat list; one commit.
  Proves: capability membership can differ per adapter.
```

```text
Step 3 — Extract specialist-depth as the first lazy capability
  · Move specialist-depth.md + the four *-deepening.md into
    capabilities/specialist-depth/, with their five corpora and tests.
  · Replace review-scope.md's hand-written hand-offs to them with a
    generated router entry.
  · Update taxonomy.md's/benchmark_taxonomy.py's path prefixes in the same
    commit (the #255 CI classifier this step originally named was
    retired by #420).
  Risk: moderate — first real move. Rollback: git revert; the corpora and
    tests move as one unit, so a revert is complete.
  Proves: the loading architecture, on the least-entangled material.
```

Why `specialist-depth` and not something else, restated against the
alternatives:

| Candidate | Why not first |
| --- | --- |
| `publication-github` | Largest single win (~16,000 words off local), but touches the mutation/authorization boundary — the highest-consequence area in the repository. Do it once the mechanism is proven. |
| `runtime-execution` | `scripts/sandbox/` is the only genuinely isolated area (0% co-change with `skills`\|`shared`), so it *looks* ideal — but its policy half is entangled with `capability-posture` and needs the §C.4 grant/deny split first. |
| `conditional-passes` | Six policies with three different activation shapes; `root-cause-consolidation` has in-degree 7 and orders another policy. More coupled than it appears. |
| `stateful-review` | Contains environment-neutral semantics currently owned nowhere else (§D.4). Extraction would force an ownership decision mid-migration. |
| **`specialist-depth`** | **Never named by either `SKILL.md`; zero co-change among members; identical link signature; explicit pre-existing activation/composition contract; five dedicated corpora; a dedicated composition corpus (A–G) that tests the routing decision itself.** If this one cannot be extracted cleanly, the architecture is wrong — which is exactly what a first step should be able to tell you. |

```text
Step 4 — Measurement harness before any further extraction
  · Establish the baseline: instruction tokens before first analysis
    (static, measurable now) plus the §I.2 quality metrics on the
    existing corpus.
  · Make the runner iterate capability corpora instead of one flat
    non-recursive glob, under the existing execution-class rules.
  Why here: Steps 1–3 are safe enough to take on structural reasoning
    alone. Step 5 onward is not — and §I.5's falsification conditions
    cannot be evaluated without this.
```

```text
Step 5 — Kernel / router separation
  · Split review-scope.md into review-scope-core (what is examined,
    canonical dimensions, restraint) and the generated router.
  · Split the three capability-boundary policies along grant/deny (§C.4).
  · Split finding.md: contract vs. fix/action-location derivation.
  · Enforce the router word budget with a tests/policy/ check.
  Risk: highest of any step — review-scope.md is the hub and #288 already
    tried once. Take it only with Step 4's baseline in hand.
```

```text
Step 6+ — Remaining capabilities, one per PR, in ascending coupling order
  scale → context-resolution → remediation → finding-placement
  → conditional-passes → runtime-execution → parallel-execution
  → reviewer-assist → stateful-review
  → authorization-github → publication-github
```

```text
Step N — Adapter thinning (last, deliberately)
  · Collapse the 13 triplicated runbook phases into one shared
    execution contract referenced by all three runbooks.
  · Only after every capability it invokes has its own home.
  Doing this earlier would mean rewriting the runbooks twice.
```

---

## K. Risks and rollback

| Risk | Likelihood | Mitigation | Rollback |
| --- | --- | --- | --- |
| **Behavior divergence** — a capability behaves differently when lazily loaded | Medium | Per-capability corpus must pass before and after each move. Steps 1–2 change no runtime behavior at all. | `git revert`; capability + corpus + tests move as one unit, so a revert is complete |
| **Benchmark regression** | Medium | §I.3's hard gate: recall, FP rate, severity accuracy and verdict consistency must not degrade, whatever the token saving | Revert the step; the baseline from Step 4 identifies which one |
| **Router becomes the new monolith** | **High — already happened once** with `review-scope.md` after #288 | §C.3's four mechanisms: word budget with a test, predicates-not-procedures, generated registration, no links to capability bodies | If the budget test fails twice in a row, stop and re-split rather than raising the budget |
| **Duplicated policies during migration** | Medium | Never copy — move. A capability's canonical rule has exactly one home throughout, per the existing `AGENTS.md` invariant. Issue #80 ("Detect canonical-rule duplication risks") is the mechanical check | Single-commit revert |
| **Safety boundary becomes bypassable** | **Low but catastrophic** | §C.4's grant/deny split. `corpus/mutation-boundary/` (28 cases) and `corpus/delegation-spawn/` (23) must pass unchanged at every step; the deny half is never lazy | Any failure here blocks the step outright — this is the one non-negotiable gate |
| **PR-time classification/selection silently changes** | **High — the mechanism is hardcoded** | Taxonomy path prefixes (`runtime_platform/benchmark/taxonomy.md`, `benchmark_taxonomy.py`) updated in the same commit as every path move, per §J.1 (the #255 `benchmark_ci_classifier.py` this risk originally named was retired by #420) | Its unit tests fail loudly if prose and code diverge |
| **Packaging drift** | Medium | Step 1's byte-identical assertion is the guard, and it stays as a regression test afterward | Checked-in manifest remains valid without the generator |
| **Version skew** | **Not applicable** | Model A keeps one version. This risk is a reason Models B and C were rejected, not a risk of the recommendation | — |
| **Cross-repo overhead** | **Not applicable** | Same as above | — |
| **Benchmark/adapter coupling persists** | **Certain** | §H.4: the split does **not** fix `benchmark_review_adapter.py`'s rendering-regex coupling. That needs #67's output schema | Must not be claimed as a benefit of this work |
| **Migration stalls half-done** | Medium | Every step leaves a coherent, shippable repository. There is no step whose value depends on a later one landing | Stop wherever; no step is a prerequisite for correctness of the ones before it |

**The single most important rollback property:** because corpus and tests
travel with their capability, a `git revert` of any step restores the
capability, its proof, and its registration together. There is no state in
which a capability exists without its benchmark.

---

## L. Follow-up issues

Proposed breakdown, responsibility-focused and sized to the repository's
existing conventions. **Not created — this record proposes them only.**

They are written to fit the established area labels
(`area:platform-contracts`, `area:packaging-portability`,
`area:review-quality`, `area:documentation`, `area:research`) and the
contribution-ownership classes in
[`../../policies/contribution-ownership-policy.md`](../../policies/contribution-ownership-policy.md).

### Architecture / platform

| # | Issue | Class | Depends on |
| --- | --- | --- | --- |
| L1 | Define the capability manifest format (`capability.yaml`): fields, activation predicates, never-clauses, benchmark location | maintainer-led, `area:platform-contracts` | this record |
| L2 | Generate `package-manifest.json` from capability manifests; assert byte-identical output | maintainer-led, `area:packaging-portability` | L1 |
| L3 | Reconcile `SKILL.md` §2, `metadata/skill.yaml` and the packaging manifest into projections of one manifest — closes the 17 undeclared policies and the missing `finding-rendering.md` declaration | maintainer-led, `area:packaging-portability` | L2 |
| L4 | Per-adapter shared subsets so each archive ships only its declared capabilities | maintainer-led, `area:packaging-portability` | L3 |
| L5 | Split the three capability-boundary policies along grant/deny; keep the deny half always-resident | **maintainer-led, security-sensitive** — explicitly *not* a contributor issue | L1 |
| L6 | Extract `review-router` from `review-scope.md`; enforce a ≤2,500-word budget with a policy test | maintainer-led, `area:platform-contracts` | L1, L11 |

### Individual capability extraction

| # | Issue | Class |
| --- | --- | --- |
| L7 | Extract `specialist-depth` as the first lazy capability (policies + 5 corpora + tests) | maintainer-led |
| L8 | Extract `scale`, `context-resolution`, `remediation` | contributor-owned, once L7 sets the pattern |
| L9 | Extract `runtime-execution` and `parallel-execution` | maintainer-led (capability boundary) |
| L10 | Extract `publication-github` and `authorization-github` | maintainer-led (mutation authority) |

### Benchmark migration

| # | Issue | Class |
| --- | --- | --- |
| L11 | Establish the performance baseline: instruction tokens before first analysis (static) + the §I.2 quality metrics | maintainer-led, `area:review-quality` |
| L12 | Make the benchmark runner iterate per-capability corpora instead of one non-recursive glob — closes "4 of ~180 cases execute" | maintainer-led; respects the #330/#391 execution classes |
| L13 | Move each corpus next to its capability, with its tests, preserving the single reference validator | contributor-owned; pairs with each extraction |
| L14 | Resolve `corpus/dependency-supply-chain-deepening/`'s missing policy owner (fifth `specialist-depth` domain, or a router-level pass) | maintainer-led |

### Performance measurement

| # | Issue | Class |
| --- | --- | --- |
| L15 | Adopt *validated useful findings / 1,000 input tokens* **with** the §I.3 no-quality-regression gate | maintainer-led, `area:review-quality` |
| L16 | Report loaded-capability count and instruction tokens in review metadata | contributor-owned; relates to #182 telemetry, must respect the telemetry ≠ ground-truth boundary |

### Documentation

| # | Issue | Class |
| --- | --- | --- |
| L17 | Update `docs/ARCHITECTURE.md` §1 module map and §7 packaging once L4 lands | maintainer-led, `area:documentation` |
| L18 | Add `docs/features/` guidance if capability loading becomes user-visible; otherwise record explicitly that it is not | contributor-owned |
| L19 | Retire the rows of `docs/large-file-decomposition.md` that capability extraction resolves | contributor-owned |

### Deliberately not proposed

- **No issue to split the repository.** §E rejects Models B and C.
- **No issue to fix `benchmark_review_adapter.py`'s rendering coupling.**
  That is #67's output schema, already open; this record only flags that
  the capability split does not address it.
- **No issue to create a capability per policy.** §M.6 lists what must not
  be split.

### Relationship to existing open issues

This record does not duplicate open work, and three existing issues become
more tractable under it:

- **#72 / #73 / #74** (Define Review Target / Review Context / Existing
  Review Evidence schema, `area:platform-contracts`) are the natural
  formalization of §G's capability inputs. The contracts here are written
  to feed those issues, not to compete with them.
- **#67 / #68** (review output schema and versioning) are what the §G
  outputs become, and are the real fix for §H.4's adapter coupling.
- **#80** (Detect canonical-rule duplication risks) is the mechanical
  check for §K's duplicated-policy risk, and §A.10 gives it two concrete
  first targets.
- **#203** (bounded review execution for oversized or context-heavy
  changes) overlaps `scale`; L8 should reconcile with it rather than
  proceed in parallel.

---

## M. Final recommendation

### M.1 Preferred architectural model

**A capability-oriented modular monorepo** with a small always-resident
kernel, a deliberately tiny generated router, and independently loadable
capabilities behind declared activation predicates. Loading is
**fail-closed**: an unloaded capability can only withhold behavior, never
grant it.

This is close to the hypothesis in the task, with two derived corrections:

- **`security` is two different things.** Security-*of-the-reviewed-code*
  (`security-deepening.md`) is a lazy review capability.
  Security-*of-the-reviewer* (mutation authority, delegation,
  trusted-host, publication authority) is a capability boundary whose deny
  half must always be resident. The hypothesis would have fused them.
- **`runtime / execution lifecycle` is not one capability.** Runtime
  *validation* (sandbox, declared commands) and *parallel execution*
  (workers, spawn budgets) have different activation predicates, different
  corpora, and different failure modes. They are two.

### M.2 Preferred repository topology

**One repository.** `capabilities/` + `adapters/` + `runtime_platform/`,
as laid out in §E.2 (renamed from `platform/` per §E.2.1 to avoid the
stdlib `platform` module collision). No split now; the manifest is what
would make a later split cheap if a genuine independent consumer ever
appears.

### M.3 What remains shared

The whole review engine. Specifically: severity and the mechanical
decision derivation, the evidence bar, the finding contract, review scope
and the dimension model, all semantic-risk and domain deepening,
architecture analysis, aggregation and consolidation, remediation
reasoning, coverage and stopping criteria, verdict consistency, and —
newly — **finding identity, finding lifecycle, and the Reviewer Brief**,
which are shared in substance today but filed as GitHub-only.

### M.4 What becomes independently loadable

`specialist-depth`, `conditional-passes`, `scale`, `runtime-execution`,
`parallel-execution`, `context-resolution`, `remediation`,
`finding-placement-derivation`, `stateful-review`, `reviewer-assist`,
`publication-github`, `authorization-github`, `repository-checkout`.

### M.5 First step

**The declarative capability manifest (§J.2, Step 1)** — additive,
byte-identical output, no runtime change. Then per-adapter subsets
(Step 2), then `specialist-depth` as the first extracted capability
(Step 3), then the measurement baseline **before** anything harder
(Step 4).

The manifest comes first because the co-change data identifies the real
constraint precisely: not the capabilities, but the two hand-maintained
registries — `review-scope.md` (25 changes) and `package-manifest.json`
(21 changes, 86% alongside `shared/policies/`) — that every capability
addition must edit by hand.

### M.6 What must explicitly NOT be split

| Do not split | Why |
| --- | --- |
| **The severity model and decision derivation** | One copy is the repository's central guarantee. It is `review-kernel`, resident, forever. |
| **The evidence bar** | Same. A per-capability evidence standard is how review quality dies. |
| **The finding contract** | Every capability's output conforms to it. Its *rendering* is already correctly separated; its *fields* must not be. |
| **The deny half of any capability boundary** | §C.4. Splitting it into a loadable unit makes it bypassable. |
| **Individual policies into individual repositories** | §E rejects Models B and C. A capability is a loading unit, not a distribution unit. |
| **The benchmark harness** | One runner, one matcher, one metric set, many corpora — the measurement architecture's standing invariant. Per-capability *corpora*, never per-capability *evaluators*. |
| **`local-code-review` and `github-pr-review` into separate engines** | §D. Thirteen runbook phases are already identical; the duplication that exists has already produced divergent taxonomies (§A.10). |
| **`git-safety.md` from `mutation-authority.md`** | Already effectively one rule — `git-safety.md` is a 191-word pointer. Fold, do not split. |
| **The six deepening policies into six capabilities** | They share one composition contract, one provenance field, and one cascading bound. Independent *evolution* (zero co-change) is an argument for independent *files*, not for six separate loading units with six activation protocols. One capability, five domains. |

### M.7 The one-sentence version

The repository does not need to be split into more repositories; it needs
**one machine-readable statement of what each review actually requires** —
which would replace the three partial, mutually inconsistent statements it
already maintains by hand.
