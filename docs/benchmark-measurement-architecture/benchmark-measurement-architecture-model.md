# Benchmark, Measurement & Analytics Architecture

Repository-development design record for the cross-component architecture
spanning the benchmark-quality-gate epic
([#329](https://github.com/amirbena/code-review-skill/issues/329) and its
tree: [#330](https://github.com/amirbena/code-review-skill/issues/330),
[#331](https://github.com/amirbena/code-review-skill/issues/331),
[#332](https://github.com/amirbena/code-review-skill/issues/332),
[#333](https://github.com/amirbena/code-review-skill/issues/333),
[#334](https://github.com/amirbena/code-review-skill/issues/334),
[#335](https://github.com/amirbena/code-review-skill/issues/335),
[#336](https://github.com/amirbena/code-review-skill/issues/336),
[#337](https://github.com/amirbena/code-review-skill/issues/337),
[#338](https://github.com/amirbena/code-review-skill/issues/338),
[#339](https://github.com/amirbena/code-review-skill/issues/339)) and the
three related measurement capabilities
([#182](https://github.com/amirbena/code-review-skill/issues/182) — review
execution telemetry,
[#131](https://github.com/amirbena/code-review-skill/issues/131) — review
analytics,
[#130](https://github.com/amirbena/code-review-skill/issues/130) —
repository-scoped learning). Not packaged; explanatory. **This document is
the canonical home for cross-component architecture only** — the dependency
order between these fourteen issues, the boundaries between their
responsibilities, and the invariants none of them may violate. Each issue
still owns its own local problem statement, scope, acceptance criteria, and
non-goals; this document does not redefine or duplicate those, and a
contradiction between an issue's local scope and this document is resolved
by updating this document through a reviewed repository change, not by
silently reinterpreting the issue.

**Stage 4 addendum.** This document was later extended, additively, to
also fix the cross-component boundaries for a second, separate set of
reliability-boundary issues raised by a review-reliability audit of two
failure modes (unsupported finding provenance; verdict drift): the
citation-grounding verification model
[#348](https://github.com/amirbena/code-review-skill/issues/348), the
benchmark citation-fidelity signal
[#349](https://github.com/amirbena/code-review-skill/issues/349), the
verdict-integrity benchmark proof
[#350](https://github.com/amirbena/code-review-skill/issues/350), and the
verdict-consistency-boundary research
[#351](https://github.com/amirbena/code-review-skill/issues/351) — see
§12. §12 is self-contained: it consumes and cross-references §1–§11
unchanged, and does not alter the fourteen-issue scope, the DAG in §2, or
the layer ownership in §3.

## 1. Problem and motivation

Four things are true about this repository's review-quality feedback loop
today, and they are easy to conflate:

1. **Deterministic/policy tests exist.** `tests/unit/`, `tests/policy/`, and
   the various reference models under `tests/reference/` already prove the
   Skills' *deterministic* logic (matching, scoring, fixture validation,
   identity derivation) behaves correctly. They do not exercise the
   Skills' actual multi-step, tool-using review *behavior*.
2. **A benchmark corpus exists.** `docs/benchmark/` ([`../benchmark/README.md`](../benchmark/README.md))
   already defines a fixture format, a growing corpus, match criteria, and
   three quality metrics (missed/incorrect findings, severity accuracy,
   duplicate noise) that *would* measure real reviewer behavior against
   known-correct expectations — if a real reviewer ever ran them.
3. **Real behavioral execution in CI is not yet dependable.** Nothing in
   `.github/workflows/*.yml` provisions a runtime capable of actually
   invoking the packaged `local-code-review` Skill's semantics.
   `docs/benchmark/ci-integration.md` §4 already documents that such a
   runtime is "almost certainly" unavailable on a bare GitHub-hosted
   runner, so the existing benchmark check can classify a PR as applicable
   and still never execute anything.
4. **Workflow telemetry, benchmark ground truth, analytics, and
   repository-scoped learning are separate concerns that need clear
   boundaries.** Four different issues (#182, #329's benchmark tree, #131,
   #130) each produce or consume review-related signal, and without an
   explicit boundary between them it is easy to conflate "what the
   reviewer inspected" with "whether the reviewer was correct," or to let
   a learned preference quietly acquire the authority of canonical policy.

The gap this document closes is not a missing feature — it is a missing
**map**. #329's three children (#330/#331/#332) already fan out into eight
further issues, each with its own detailed scope, and #182/#131/#130 each
reference the others informally ("relates to", "distinct from"). Without
one place that fixes the dependency order and the layer boundaries, that
informal cross-referencing drifts: a later issue could re-derive (and
subtly diverge from) an architectural decision another issue already made,
or two issues could silently duplicate a responsibility neither fully owns.
This document is that one place.

## 2. Canonical dependency DAG

```text
#330 → #336 → #337 → (#333 → #334 || #338 → #339 → #332) → #335 → #331 → #329 → (#182 + #329) → #131 → #130
```

This is a **practical build/trust order**, not a literal redraw of every
native GitHub `Depends on` / `Blocks` / parent-child edge — those native
edges (recorded on each issue and summarized in §2.1 below) already exist
and are not changed by this document. The DAG above states the order in
which the work actually becomes *usable*, which is stricter than the
native edges in one place worth calling out explicitly (§2.2).

Read left to right:

- **#330 → #336 → #337** — the runtime foundation is sequential and
  single-threaded: #330 fixes the vendor-neutral execution *contract*
  (what any runtime must satisfy), #336 is the empirical spike that scores
  real candidates against that contract, and #337 provisions the runtime
  #336's decision record names. Nothing downstream has a real runtime to
  execute against until #337 lands.
- **`(#333 → #334 || #338 → #339 → #332)`** — two independent branches
  fan out from the provisioned runtime and run in parallel:
  - the **PR-time branch**, #333 (canonical taxonomy + inverted index)
    then #334 (deterministic Top-K selector + coverage policy) — see §5;
  - the **nightly branch**, #338 (scheduled full-corpus execution +
    history) then #339 (drift detection + regression issue lifecycle),
    which together constitute #332 — see §6.

  These two branches share no code and no scheduling dependency on each
  other; they are drawn in parallel (`||`) because both only need #337's
  runtime to exist, not each other's output. #339 additionally depends on
  #338's persisted history (an in-branch dependency), and #332 is the
  tracking parent that both children complete.
- **→ #335** — shadow-validation is the join point: it needs #334's
  informational selector *and* #332's nightly history (i.e., #339's
  completed drift-detection loop) as its evidence source, so it cannot
  start meaningfully until both branches have produced real output.
- **→ #331 → #329** — #335's evidence-backed required-gate transition is
  the last of #331's three children, so #331 (the Top-K-gate tracking
  parent) completes; #331 completing alongside #330 and #332 completing is
  what closes #329 (the whole epic's tracking parent).
- **→ (#182 + #329) → #131 → #130** — #131 (analytics) is deliberately
  gated on **both** #182 (telemetry exists to report workflow-observation
  metrics from) and #329 (a trustworthy benchmark-quality signal exists to
  report ground-truth metrics from) — see §7. #130 (learning) in turn
  needs #131's measurement foundation in place before repository-scoped
  feedback can be reused safely.

### 2.1 Native tracker edges (as recorded on each issue)

| Issue | Parent | Depends on | Blocks / children |
| --- | --- | --- | --- |
| #329 | — | — | children: #330, #331, #332 |
| #330 | #329 | — | blocks #331, #332; children: #336, #337 |
| #336 | #330 | #330 | blocks #337 |
| #337 | #330 | #330, #336 | — |
| #331 | #329 | #330 | children: #333, #334, #335 |
| #333 | #331 | #330 | blocks #334 |
| #334 | #331 | #333, #330 | blocks #335 |
| #335 | #331 | #334, #332 | — |
| #332 | #329 | #330 | children: #338, #339 |
| #338 | #332 | #330 | blocks #339 |
| #339 | #332 | #338 | — |
| #182 | — | relates #131 | — |
| #131 | — | #44 (open, not in this doc's scope) | — |
| #130 | — | #42, #43 (both delivered) | — |

### 2.2 Where the practical order is stricter than the native edges

The native edges alone would let #333/#334 (PR-time branch) and #338
(nightly branch) proceed once **#330** merely exists as a documented
contract, since that is the literal `Depends on: #330` recorded on each.
In practice, both branches need a runtime that actually
`check_runtime_available()`-succeeds to produce anything but
`runtime-unavailable`/`insufficient-coverage` placeholder outcomes — which
is #337's deliverable, not #330's. The DAG in §2 threads the build order
through #337 explicitly for this reason. This is a sequencing
clarification, not a change to any issue's recorded dependency — #333,
#334, and #338 are free to *start* (design, tests against synthetic data)
before #337 lands; they cannot produce a real, evidence-backed result
before it does.

Similarly, #131's dependency on #329 is not a native tracker edge (#329
does not list #131 as a blocker, and #131's own `Dependencies` section
only names #44). It is this document's architectural judgment, recorded
here rather than invented silently in #131's implementation: reporting
"benchmark-derived quality metrics" (part of #131's stated scope) requires
a trustworthy benchmark signal to exist, which is exactly what #329
delivers. §7 states this boundary normatively. If a future contributor
finds this judgment wrong (e.g. #131 should ship with benchmark metrics
simply marked `unavailable` until #329 lands, rather than waiting), that
is a genuine architectural question to resolve by updating this document,
not by quietly starting #131 early.

## 3. Architecture layers

Nine responsibilities, each with exactly one owner. A layer never
re-implements another layer's logic; it consumes the layer(s) below it
through their existing contracts.

| Layer | Responsibility | Owner | Consumes |
| --- | --- | --- | --- |
| **Runtime execution** | Actually invoking the packaged `local-code-review` Skill's real, unmodified semantics inside an isolated, non-personal CI environment. | #330 (contract) → #336 (candidate evidence) → #337 (provisioning) | Nothing below it — this is the foundation. |
| **Benchmark candidate taxonomy/indexing** | A small, closed, alias-free classification vocabulary for both corpus cases and PR diffs, and a precomputed inverted index for cheap candidate lookup. | #333 | Runtime execution (its one bounded model call — PR-diff classification — runs through #330/#337's runtime/credential path). |
| **Bounded PR-time benchmark selection** | Turning a narrowed candidate pool into a deterministic, explainable, coverage-bounded Top-K set of cases to actually execute for a given PR. | #334 | Taxonomy/indexing (candidate pool, PR classification); runtime execution (to run the selected cases). |
| **Pre-merge behavioral gating** | Deciding whether/when the PR-time selection becomes a required, fail-closed branch-protection check, and the evidence bar that justifies that promotion. | #335 | PR-time selection (the thing being validated); nightly history (the broader-evidence comparison source). |
| **Nightly full-corpus execution/history** | Running the entire corpus on a schedule and persisting comparable, interpretable results over time. | #338 | Runtime execution. |
| **Drift detection / regression issue lifecycle** | Comparing persisted nightly runs, deciding what counts as meaningful drift, and managing one deduplicated GitHub issue per regression. | #339 | Nightly history (#338); the existing `regression-report.md`/#55/#56/#57 metrics (reused, not reimplemented). |
| **Review execution telemetry** | Observational record of what a review actually inspected/executed (files, symbols, expansions, runtime validations, partitions, stages) — never decision-affecting. | #182 | Nothing above — it observes the ordinary review process, independent of the benchmark tree. |
| **Analytics / quality exports** | A consolidated, denominator-defined view of workflow-observation metrics (from telemetry) and benchmark-derived quality metrics (from the benchmark tree), kept explicitly separate. | #131 | Review execution telemetry (#182); benchmark-derived ground truth (#329's tree, once trustworthy). |
| **Repository-scoped learning** | Using eligible, explicit accepted/rejected/resolved finding feedback to improve future precision within one repository, with policy always authoritative. | #130 | Analytics/measurement foundation (#131); the existing finding-identity/lifecycle model (#42/#43). |

Layers are listed top-to-bottom in dependency order, but note two
independent sub-graphs: **runtime execution → taxonomy/indexing → PR-time
selection → pre-merge gating** is one chain, and **runtime execution →
nightly execution/history → drift detection** is a second, parallel chain
that only rejoins the first at the pre-merge-gating layer (which needs
nightly history as validation evidence, per §2). **Telemetry** is an
independent ninth layer with no dependency on the benchmark tree at all —
it observes live workflow behavior, not benchmark ground truth. **Analytics**
is the first layer to deliberately draw from two otherwise-unrelated
sources (telemetry and benchmark ground truth), and **learning** is the
only layer built on top of analytics rather than on top of the benchmark
or telemetry layers directly.

## 4. Runtime contract

The stable architectural rules that #330 establishes, #336 evaluates
against, and #337 provisions — restated here at the level a consumer of
the runtime (#333's PR-diff classification call, #334's selected-case
execution, #338's nightly full-corpus execution) needs, without
re-litigating #330's full candidate evaluation.

```text
benchmark runner (run_benchmark.py, unchanged)
  → ReviewerAdapter (the existing abstraction boundary — vendor-neutral)
    → compatible agent CLI/runtime  (candidate-specific, swappable)
      → actual Skill (local-code-review, unmodified, unforked)
        → model backend  (candidate-specific, swappable)
```

Rules that hold regardless of which runtime is ultimately selected:

- **Vendor-neutral.** What is under evaluation is the Skill's actual
  behavior — its review-scope passes, its finding contract, its
  evidence/confidence model — not any single CLI vendor's product. Any
  execution vehicle that can genuinely invoke that behavior with high
  fidelity is a legitimate candidate.
- **Actual Skill semantics, not a second reviewer implementation.** A
  runtime that needs the Skill re-described in a different prompt/agent
  format to run is disqualified — that would become a second,
  unofficial reviewer that could drift from the packaged source. The
  `ReviewerAdapter` boundary stays a thin adapter around an unmodified
  `SKILL.md`/`policies/`/`shared/`, never a translation layer that
  reimplements the Skill.
- **No maintainer personal machine, session, or credentials.** This is a
  trust-boundary requirement, not an availability optimization. No
  repository-controlled workflow — including one triggered by a PR the
  maintainer did not author — may have a code path reaching the
  maintainer's personal workstation, filesystem, shell, SSH state,
  browser/session state, or personally-authenticated CLI session, under
  any trigger, including fork PRs.
- **Isolated CI execution.** Runs in an environment dedicated to CI, never
  a device also used for anything else; credentials are purpose-specific,
  minimally scoped, and independently revocable; fork PRs and other
  untrusted input stay separated from any secret-bearing execution path.
- **Replaceable runtime/provider.** The `ReviewerAdapter` boundary is what
  keeps the runtime swappable — changing providers later must not require
  touching the runner, matcher, metrics, selector (#334), or nightly
  pipeline (#338/#339).
- **Runtime/model/Skill metadata recorded with every benchmark result.**
  At minimum: runtime/CLI name and version, model/backend identifier and
  version/tag where exposed, and the Skill/repository SHA the review ran
  against. Every consumer of a benchmark result (#334's PR-time run,
  #338's nightly run, #131's benchmark-derived exports) can therefore
  attribute a result change to a Skill change versus a runtime/model
  change, rather than having the two silently confounded.
- **Free/near-zero cost is preferred, not sacrificed-for-fidelity
  blindly.** A cheaper candidate that cannot actually invoke the Skill's
  real multi-step, tool-using semantics is not viable regardless of cost;
  among candidates that clear fidelity, cost, latency, reproducibility,
  and operational complexity are all legitimate comparison axes.

**This document does not hard-code the final runtime choice.** #336 owns
the empirical evaluation of concrete candidates, and #337 owns
provisioning whatever #336's decision record names. Nothing above commits
to Claude Code, Anthropic's backend, or any other specific vendor as an
architectural requirement — the contract is satisfied by any runtime that
meets these rules, and the *rejected* classes (a self-hosted runner
reusing the maintainer's personal session; a bare single-shot completion
endpoint standing in for the Skill's actual tool-use loop) are rejected on
these architectural grounds, not on vendor identity.

## 5. PR benchmark path

Stable principles only, drawn from #331/#333/#334/#335. Exact scoring
weights, band thresholds, and the Top-K default/ceiling are #334's
implementation detail, recorded there, not architectural commitments of
this document.

```text
PR diff
  → canonical taxonomy classification            (#333)
  → inverted-index candidate narrowing            (#333)
  → deterministic relevance/coverage selection    (#334)
  → bounded Top-K                                 (#334)
  → real benchmark execution                      (#330/#337's runtime)
  → informational first                           (#334)
  → required gate only after evidence             (#335)
```

Principles that hold regardless of the exact numbers chosen:

- **No full-corpus scan on the PR critical path.** Selection always
  narrows through #333's precomputed inverted index first; nothing in this
  path scores or scans the whole corpus per PR.
- **No embeddings or semantic-search selector.** The only model call
  anywhere in this path is #333's one bounded, schema-constrained PR-diff
  classification step. Relevance and coverage scoring downstream of that
  are pure deterministic computation over taxonomy tags — never a second
  model call, never a vector/embedding similarity search.
- **Canonical closed taxonomy.** Classification may only select from a
  small, fixed, alias-free enum; an unconfident dimension resolves to an
  explicit `unclassified` value, never an invented key and never a silent
  guess.
- **Deterministic scoring/coverage.** Case relevance and selection
  coverage are two distinct, reproducible, unit-testable computations —
  the same candidate pool and PR classification always yield the same
  selection.
- **`insufficient-coverage` and runtime-unavailable are explicit
  outcomes.** Neither may render as a silently passing/green result; both
  are distinct, visible states the workflow reports.
- **Promotion to a required gate happens only after shadow validation.**
  #334's selector ships and runs informationally first. #335 owns the
  entire promotion decision — measuring miss rate and over-selection
  against #332's nightly results over a burn-in window, and only then
  moving `benchmark-check.yml` into required branch-protection status,
  with an explicit, auditable (never silent, never standing) override for
  a maintainer to unblock a specific failing outcome.

## 6. Nightly path

Stable principles drawn from #332/#338/#339. Exact storage implementation
and exact drift/noise thresholds are #338's and #339's implementation
detail, not recorded here.

```text
nightly trusted execution        (#338, scheduled + workflow_dispatch, main only)
  → full corpus                  (#338, run_benchmark.py with no case filter)
  → persisted comparable history (#338, keyed by date + commit SHA + runtime metadata)
  → baseline/reference comparison(#338's chosen baseline policy)
  → meaningful drift detection   (#339, reusing regression-report.md/#55/#56/#57 unchanged)
  → deduplicated issue lifecycle (#339)
```

Principles that hold regardless of the exact storage/threshold choices:

- **Never blocks PR or main.** The nightly workflow runs on a `schedule:`
  trigger against `main` (or a maintainer-chosen ref) and never gates a
  merge or deployment, under any outcome.
- **Baseline policy must avoid silent drift ratcheting.** A naive
  "always compare to yesterday's run" policy lets a small degradation
  become tomorrow's accepted baseline, silently eroding the known-good
  reference over time. #338 evaluates and documents an explicit baseline
  policy (last-known-good, a deliberately-refreshed pinned reference, a
  noise-dampening rolling baseline, or a justified combination) rather
  than defaulting to the ratcheting shape.
- **History is benchmark ground truth.** The persisted nightly history is
  kept structurally separate from #131's workflow-observation export and
  #182's execution telemetry — never mixed into packaged Skill resources
  or an existing `docs/` analytics surface. It is the authoritative
  benchmark-quality record §7's "benchmark ground truth" layer refers to.
- **Drift issues are fingerprinted, deduplicated, updateable, and
  resolvable.** #339 reuses the existing `regression-report.md` contract
  and #55/#56/#57 metrics unchanged; it adds the policy for what counts as
  *meaningful* drift versus noise, a stable fingerprint from already-stable
  identifiers, and full issue lifecycle (open once, comment on recurrence,
  auto-close on resolution, never auto-close over an explicit maintainer
  `keep-open` override).

## 7. Measurement / analytics / learning boundaries

Four capabilities produce or consume review-related signal. Each answers a
different question, and none may be substituted for another.

| Capability | Question it answers | Decision-affecting? |
| --- | --- | --- |
| **#182 — execution telemetry** | What did the reviewer actually inspect and execute (files, symbols, repository-intelligence expansions, runtime validations, partitions, stage completion)? | **Never.** Purely observational; cannot influence findings, severity, suppression, or the decision. This is a deliberately different model from the *decision-affecting* coverage concept in `shared/policies/review-stopping-criteria.md` — #182 does not copy or extend that model. |
| **#329's benchmark tree — ground-truth behavioral evaluation** | Did the reviewer behave *correctly* against known cases with known-correct expected findings? | Indirectly, through the gate: once #335 promotes it, an `insufficient-coverage` or `runtime-unavailable` outcome can fail a required merge check. The benchmark *result itself* never edits a live review's findings — it gates merges of Skill changes, a different mechanism from telemetry. |
| **#131 — analytics** | Consolidated, denominator-defined view of observed workflow behavior over time (from #182) and benchmark-derived quality metrics (from #329's tree), kept explicitly separate. | No. Analytics reports on past behavior; it does not feed back into any live review. |
| **#130 — learning** | May accepted/rejected/resolved reviewer feedback, once eligible and repository-scoped, improve future review precision? | Only within the bounds #130 defines: canonical policy always wins a conflict, a single rejection never suppresses a later legitimate defect, and any material learned influence is auditable and reversible. |

The four boundary statements this document fixes, so a future contributor
cannot casually conflate them:

- **Telemetry ≠ benchmark ground truth.** #182 records what happened
  during a review; #329's tree records whether the reviewer was *right*
  against known-correct cases. A review can have full telemetry coverage
  and still be behaviorally wrong, and a benchmark case can be evaluated
  with no telemetry involved at all. Neither substitutes for the other,
  and #131 must not report one as if it were the other.
- **Benchmark ground truth ≠ live workflow analytics.** #329's tree only
  ever runs against the fixed, versioned corpus under
  `docs/benchmark/corpus/`, in CI, never against a real user's PR.
  `docs/benchmark/regression-report.md` already disclaims live-workflow
  analytics for exactly this reason; #131 keeps that disclaimer intact by
  never conflating the two datasets, reporting ground-truth-dependent
  metrics as unavailable rather than estimated wherever no ground truth
  exists for a given population.
- **Analytics ≠ learning.** #131 reports on past behavior in aggregate;
  it does not change how any future review runs. #130 is the only layer
  in this document that is allowed to feed a signal back into future
  reviewer behavior, and only through its own eligibility, decay, and
  audit machinery — never implicitly through #131's exports being read as
  training signal.
- **Learned knowledge ≠ canonical policy.** Whatever #130 learns from
  repository-scoped feedback never gains the authority of
  `shared/policies/` or a Skill's own `policies/`. A learned preference
  can inform a future review's phrasing or prioritization; it can never
  override, suppress, or weaken a canonical policy rule, and #130's own
  acceptance criteria require fixtures proving policy wins that conflict.

#329 (the benchmark epic) does not implement or formally sequence
#182/#131/#130 — it only establishes a reliable benchmark-quality signal
that #131 may later consume. The dependency §2 draws from #329 (and #182)
into #131 is this document's architectural judgment about *when it is
meaningful* to report ground-truth metrics (once they exist and are
trustworthy) and observational metrics (once telemetry exists to source
them from) — not a claim that #329 defines #131's scope.

## 8. Cross-cutting invariants

These hold across every layer in §3, regardless of which issue is being
implemented:

- **No duplicate reviewer/runner/evaluator implementations.** Every layer
  consumes the existing `run_benchmark.py` runner, `ReviewerAdapter`
  boundary, matcher, and metrics (#54/#55/#56/#57) through their existing
  contracts. No issue in this tree builds a second reviewer, a second
  runner, or a second evaluator.
- **No personal-machine CI path.** Restated from §4: no code path in any
  workflow this document's tree adds may ever reach the maintainer's
  personal machine, credentials, filesystem, shell, SSH state, or
  browser/session state, under any trigger including fork PRs.
- **Bounded PR-time cost/runtime.** The PR-time path (§5) always executes
  a small, fixed-ceiling number of cases (#334's Top-K bound), never an
  open-ended or corpus-sized job.
- **No full corpus in the merge critical path.** Full-corpus execution is
  exclusively #338's nightly job; nothing on the PR-time path scans or
  executes the entire corpus.
- **Nightly is non-blocking.** Restated from §6: the nightly workflow
  never gates a PR merge or a deployment to `main`, under any outcome.
- **Benchmark history separated from ordinary workflow telemetry.**
  #338's persisted nightly history, #182's execution telemetry, and #131's
  analytics export are three structurally distinct artifacts/storage
  locations — never merged into one, never cross-written by another
  layer's code path.
- **Canonical policy remains authoritative over learned behavior.**
  Restated from §7: #130's learning layer can never acquire the authority
  of a canonical policy file.
- **Issues own execution slices; this design doc owns cross-component
  architecture.** Each of the fourteen issues in scope retains its own
  local problem statement, implementation scope, acceptance criteria, and
  non-goals. This document never redefines those locally-owned details; it
  only fixes the order, the boundaries, and the invariants between them.
  If implementation reveals a genuine architectural contradiction or a
  missing invariant, the fix is a reviewed change to this document, not a
  local reinterpretation inside a single issue.

## 9. Non-goals

- **No implementation.** This document ships no runtime, selector,
  nightly workflow, analytics export, or learning behavior. It is
  architecture and documentation normalization only; every concrete
  behavior is implemented and validated by its owning issue.
- **No scoring constants, thresholds, or storage schemas.** Exact
  relevance weights, coverage percentages, Top-K bounds, drift tolerances,
  baseline-refresh cadence, and storage formats are implementation
  decisions that live in #333/#334/#335/#338/#339, not architectural
  commitments recorded here.
- **No runtime/vendor selection.** §4 fixes the contract every candidate
  must satisfy; #336 evaluates candidates against it and #337 provisions
  the winner. This document names no winner.
- **No reassignment of tracker metadata.** This document changes no
  issue's assignee, label, native parent/sub-issue relationship,
  dependency edge, or state. §7's #131-depends-on-#329/#182 judgment is
  recorded as architectural guidance for how #131 should be scoped and
  sequenced in practice; it is not a native tracker edge this document
  adds on #131's or #329's behalf (see §2.2).

## 10. Smallest useful first implementation

1. **This model** — the dependency DAG (§2), the nine architecture layers
   and their single owners (§3), the vendor-neutral runtime contract (§4),
   the PR-time and nightly path principles (§5, §6), and the
   telemetry/benchmark/analytics/learning boundary (§7) — consumed as the
   canonical reference every one of the fourteen issues points back to.
2. **A compact "Canonical design" section on each of the fourteen
   issues**, naming this document and the issue's own local
   responsibility and relevant sections, so implementation work starts
   from this shared map rather than re-deriving it per issue.
3. **Conservative compression of duplicated architectural prose** in the
   issues, where this document already states it canonically — while
   preserving every issue's local problem statement, scope, dependencies,
   and acceptance criteria untouched.

**Deferred** (named here so scope stays fixed):

- any actual runtime, selector, workflow, taxonomy, index, storage,
  drift-detection, telemetry, analytics, or learning implementation —
  all of #330–#339, #182, #131, #130's own scope, unchanged by this
  document;
- picking a winning runtime candidate (#336's empirical spike);
- setting concrete scoring/coverage/drift thresholds (each owning issue's
  own decision, informed by its own burn-in/validation data).

## 11. Relationship to existing canonical policies and docs

- [`../benchmark/README.md`](../benchmark/README.md) owns the benchmark
  contracts this architecture sits above: fixture format, corpus, runner
  contract, match criteria, the three quality metrics, and the existing
  informational CI wiring (`ci-integration.md`, #255). This document adds
  the runtime/selection/nightly/measurement architecture on top; it does
  not redefine any of those contracts.
- [`../finding-confidence/README.md`](../finding-confidence/finding-confidence-model.md)
  owns the finding `confidence` field that runtime-validated and
  benchmark-derived evidence roll into; unrelated to this document's
  scope beyond both ultimately informing review-quality signal.
- `shared/policies/review-stopping-criteria.md` owns the
  *decision-affecting* coverage concept that #182's telemetry is
  explicitly distinct from (§7).
- `docs/benchmark/regression-report.md` owns the run-to-run comparison
  contract #339 reuses unchanged (§6), and already disclaims
  live-workflow analytics — the disclaimer §7 keeps intact for #131.
- [`../ARCHITECTURE.md`](../ARCHITECTURE.md) is the repository-wide
  system map; this document is referenced from its "Repository-development
  instrumentation" section rather than duplicating that map's content.
- `shared/policies/severity.md` owns the mechanical severity → decision
  derivation; §12.4's verdict-integrity work checks a live review's
  rendered output against that derivation and never redefines it.
- `shared/policies/architectural-placement.md` and
  `shared/templates/finding.md` own, respectively, the caller/callee
  evidence requirement for a placement finding and the finding `location`
  / `evidence location` field semantics; §12.2's citation-grounding work
  verifies against both but never redefines either.

## 12. Stage 4 — Reliability boundaries: provenance, citation fidelity, and verdict integrity

Repository-development addendum for two reliability gaps identified by a
review-reliability audit of this repository's own Skills, spanning both
`local-code-review` and `github-pr-review`:

- **(A) Unsupported finding provenance** — a reviewer reporting a finding
  about code it did not actually inspect (a claimed missing check that
  actually exists in a caller/helper it skipped; a finding reasoned from
  structural shape without following the relevant execution path; a
  plausible finding without enough concrete evidence to prove the cited
  code was ever read).
- **(B) Verdict drift** — a review body containing blocking (P0/P1)
  findings while the rendered top-level outcome still reads as clean.

Neither failure mode requires redesigning anything §1–§11 already
establish. Both are new *consumers of*, or *deterministic checks over*,
existing layers this document already governs: the telemetry layer (§7,
#182), the benchmark tree (§2/§5/§6, `docs/benchmark/`), and the
mechanical severity → decision contract (`shared/policies/severity.md`,
unchanged, §11). This section exists so that the same conflation §7
already warns against for the original four capabilities — telemetry
read as ground truth, ground truth read as live analytics, analytics read
as learning — is not repeated one layer up for provenance and verdict
integrity.

### 12.1 Three kinds of assurance, not one

Work in this space spans three categories that must stay as
distinguishable from each other as §7's four capabilities are:

| Kind | Answers | Can it gate a live review? |
| --- | --- | --- |
| **Observational telemetry** | What did the reviewer's own execution actually touch (files, symbols, expansions, validations)? | Never. This restates, and does not re-derive, §7's existing rule for #182 — every consumer named below, including citation-grounding, inherits it unchanged. |
| **Benchmark evidence** | Does a produced finding's citation correspond to real, checkable facts — an existing location, a correct fixture match, a genuinely non-clean verdict — when run against the versioned corpus? | Indirectly, only through the existing gate mechanism §5/§7 already define (promotion to a required merge check). Benchmark evidence about citation fidelity or verdict integrity follows the exact same rule as every other benchmark signal in §7: it measures correctness against known cases, and it never edits a live review's findings or decision. |
| **Runtime enforcement** | Should a live review's own output (findings, rendered verdict, published GitHub event) be mechanically checked or corrected before or at publication? | Only if a future, separately-scoped issue explicitly says so and is built. Nothing named in this section is runtime-enforcing by default. Each subsection below states plainly whether it is observational, benchmark-only, or a research question about enforcement, and none may upgrade itself into the next category by implication. |

### 12.2 Provenance / citation-grounding verification (extends §7's telemetry boundary)

A finding's cited `location` / `evidence location`
(`shared/templates/finding.md`) existing and being accurately quoted is a
different claim from that citation having been produced by actually
inspecting the code, per `shared/policies/architectural-placement.md`'s
bounded caller/callee ladder ("Bounded context expansion", "Evidence").
§7 already fixes that #182 is purely observational and can never become
decision-affecting; this subsection extends that same boundary to its
first proposed consumer rather than opening a new one:

- **Citation-grounding verification model**
  ([#348](https://github.com/amirbena/code-review-skill/issues/348)) —
  design work only: defines what "this finding's citation is grounded in
  #182's recorded inspection" means, as a specification consuming #182's
  telemetry schema as given. It does not modify #182's scope or its
  observational boundary, and it explicitly does not decide whether
  grounding should ever gate anything — that question is deferred (below)
  until real signal exists to evaluate it against.
- **Citation-grounding cross-check** (named here, **not yet tracked as an
  issue** — see §12.5) — the actual consumer that would cross-reference a
  finding's citation against #182's recorded inspected-files/symbols set.
  Per §12.1's table this is **observational only** for as long as it
  exists without a separate, explicitly-scoped enforcement issue: it may
  report a citation as outside recorded inspection, but per §7's
  unchanged rule it may not suppress, downgrade, escalate, or otherwise
  influence that finding's severity, confidence, or the decision.
  Whether it should ever be allowed to do so is an intentionally separate
  future research question, itself deferred until this cross-check has
  produced real data — never decided by implication inside the
  cross-check's own implementation.

### 12.3 Benchmark citation-fidelity signal (extends the benchmark tree, §2/§5/§6)

A mechanical check that a produced finding's cited file/line/snippet
actually exists at the reviewed SHA — independent of whether it was
*inspected* (§12.2) or *matches a fixture*
(`docs/benchmark/match-criteria.md`, unchanged). Per §12.1's middle row
this is benchmark evidence: it runs against the corpus/harness, never
against a live review, and it does not require #182's telemetry to exist.

The tracking issue for this signal is
[#349](https://github.com/amirbena/code-review-skill/issues/349). It does
require the benchmark harness to actually carry a produced finding's real
location/claim content through to any check that inspects it — the same
fidelity gap #342 (open, P1) already tracks for the *matcher*. This
signal is a second, independent consumer of that same
fix, not a restatement of #342's scope: #342 repairs
`benchmark_review_adapter.py`'s claim/location extraction so the matcher
can correctly pair a produced finding against an expected fixture entry;
this signal is a new, additional check built on top of that repaired
extraction, asking a different question ("does the citation exist at
all, against the real repository at the reviewed SHA") than the
matcher's own question ("does the citation correspond to the expected
fixture entry").

### 12.4 Verdict integrity: benchmark proof and the consistency-boundary research

Restated from `shared/policies/severity.md`, "Decision derivation
(mechanical)" (unchanged by this document, and not redefined by anything
named in this section): the severity → decision derivation is already
specified as mechanical, single-pass, and applying identically wherever
the decision is rendered. The reliability gap is that nothing *executes*
that specification against a live review's own rendered surfaces — its
findings list, its Result/Decision line, and, for `github-pr-review`, the
GitHub review event it submits — before publication. Two clearly
separated tracks close this gap, per §12.1's benchmark-evidence /
runtime-enforcement boundary:

- **Benchmark proof**
  ([#350](https://github.com/amirbena/code-review-skill/issues/350)) —
  an end-to-end corpus fixture with an unambiguous blocking defect, run
  through the real packaged Skill, asserting the rendered outcome is
  never the clean/approved value. This is benchmark-only: it demonstrates
  the mechanical rule holds today against real output. It builds no
  enforcement mechanism and changes nothing in a live review.
- **Consistency-boundary research**
  ([#351](https://github.com/amirbena/code-review-skill/issues/351)) —
  the deliberately separate question of whether a deterministic runtime
  step should exist that reconciles
  the three rendered surfaces before or at publication, and if so, where
  it should live, what it consumes (the existing markdown templates today
  versus a future machine-readable schema — see #67/#71, both open), and
  what it does on a detected mismatch. This research does **not** redesign
  `severity.md`'s derivation: the boundary it is scoped to design only
  ever *checks* that derivation's output against what was actually
  rendered and published, and never recomputes severity or the decision
  by a second, independent path — the same governance rule
  `tests/reference/review/decision_semantics.py`'s
  `PROHIBITED_OVERRIDE_PARAM_FRAGMENTS` / `PROHIBITED_CORRECTION_FRAGMENTS`
  already encode for the reference module applies to any future
  implementation this research recommends. Any actual implementation is
  out of this research issue's own scope and deferred until the research
  concludes.

### 12.5 What this section tracks now versus defers

Consistent with §9's non-implementation stance and §10's staged-rollout
pattern:

- **Tracked as issues by this update**: the citation-grounding
  verification model
  ([#348](https://github.com/amirbena/code-review-skill/issues/348),
  §12.2 first bullet); the benchmark citation-fidelity signal
  ([#349](https://github.com/amirbena/code-review-skill/issues/349),
  §12.3); the verdict-integrity benchmark proof
  ([#350](https://github.com/amirbena/code-review-skill/issues/350),
  §12.4 first bullet); the verdict-consistency-boundary research
  ([#351](https://github.com/amirbena/code-review-skill/issues/351),
  §12.4 second bullet).
- **Named but deliberately not yet filed**: the citation-grounding
  cross-check (§12.2, second bullet) — hard-blocked on #182's telemetry
  landing and on the grounding model above concluding first; filing it
  earlier would create an issue with no schema to design against. Also
  not yet filed: any decision about whether grounding should gate
  confidence or severity (evaluated only after the cross-check has run
  and produced data), and any implementation of the consistency boundary
  (evaluated only after the research above concludes). Naming them here,
  unfiled, keeps this document's map complete without opening issues that
  cannot yet make progress.
- **Explicitly not redefined by this section**: #182's observational
  boundary (§7, unchanged); the benchmark match/fixture/runner contracts
  (`docs/benchmark/`, unchanged); and `shared/policies/severity.md`'s
  mechanical derivation (unchanged). Every item above is a consumer of,
  or a check over, these existing contracts — never a replacement for one
  of them.
