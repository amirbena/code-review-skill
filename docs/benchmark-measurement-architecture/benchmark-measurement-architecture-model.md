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
execution telemetry, implemented in-repo;
[#131](https://github.com/amirbena/code-review-skill/issues/131) — review
analytics; and
[#130](https://github.com/amirbena/code-review-skill/issues/130) —
repository-scoped learning). **#131 and #130 are closed `not planned`** as
product-layer capabilities outside this Skill's scope — see the
Product-layer boundary decision addendum below. Not packaged; explanatory.
**This document is the canonical home for cross-component architecture
only** — the dependency order between the **twelve actively-implemented
issues** (#131 and #130 excluded, per the addendum below), the boundaries
between their responsibilities, and the invariants none of them may
violate. Each issue still owns its own local problem statement, scope,
acceptance criteria, and non-goals; this document does not redefine or
duplicate those, and a contradiction between an issue's local scope and
this document is resolved by updating this document through a reviewed
repository change, not by silently reinterpreting the issue.

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

**Execution-model revision
([#391](https://github.com/amirbena/code-review-skill/issues/391)).**
Unlike the Stage 4 addendum above, this revision **does** change §2's DAG
and part of §4's runtime contract, directly — it is a structural
correction, not an additive extension. #330's original contract, and this
document's §2/§4/§6, assumed a single execution class: a dedicated,
provisioned CI runtime (#337) that #336's empirical spike would select a
candidate for. That spike (and its #366 follow-up, closed without
merging) found no candidate clears the contract's own viability bar at an
acceptable cost —
[`../benchmark/runtime-candidate-decision.md`](../benchmark/runtime-candidate-decision.md)
records the evidence, kept as historical record and **not reopened** by
this revision. #391 responds architecturally: the runtime contract splits
into two execution classes (§4), #337 is superseded and no longer
load-bearing anywhere in §2's DAG, and the maintainer-controlled class's
selected scheduled-integration target is Claude Cloud Routines. §2 and §4
are revised below; §2.3 records the exact, bounded wording corrections
this revision's downstream issues (#331/#332/#335/#338/#339) still need,
deferred to separate, later changes rather than applied here. §3, §5, §7,
§8 (except one restated bullet), §9 (except one bullet), §10, §11, and
§12 are otherwise unaffected.

**Legacy CI retirement
([#420](https://github.com/amirbena/code-review-skill/issues/420)).** By
the time §5's PR-time path below was fully implemented (#333's taxonomy
and inverted index, PR #418; #334's deterministic Top-K selector, PR
#419), the original #255 PR-level GitHub Actions check
(`.github/workflows/benchmark-check.yml` and
`scripts/benchmark/benchmark_ci_classifier.py`) had become a redundant
third execution path: its own PR-diff applicability decision duplicated,
less precisely, what #333/#334 now compute deterministically, and #391
had already made its non-blocking contributor-path status permanent
rather than a stepping stone to a provisioned Class 1 runtime. #420
removed that workflow and classifier, and the doc that specified them
(`docs/benchmark/ci-integration.md`), completely. This does not change
§2's DAG or §4's two-class split — it removes a workflow that was never
part of either — but it does correct §5's promotion-mechanism bullet
(previously naming `benchmark-check.yml` as the eventual required-gate
target) and §11's `ci-integration.md` cross-reference. There is no
independent GitHub Actions benchmark execution path left over from #255.
#420 was tracked as a fourth child of #331 alongside #333/#334/#335 (§2.1),
since retiring the redundant legacy path is part of confirming the
Top-K-gate tracking parent's children collectively cover the PR-time
benchmark path with no gap or duplicated ownership.

**Product-layer boundary decision (#130/#131 — closed `not planned`).**
#131 (review analytics) and #130 (repository-scoped learning) — the last
two links in §2's original DAG tail (`... → #131 → #130`) — are closed as
`not planned` for implementation inside this Skill. Both require
persisted, cross-invocation state: #131's historical aggregation
(accepted/rejected rates, recurrence, resolution latency, retention,
cross-review aggregation) and #130's learned behavior from stored
reviewer feedback. `code-review-skill` is intentionally an
action-oriented, invocation-scoped Skill: its responsibility is to
perform a code review for the current invocation and emit the
evidence/output that invocation requires. It does not own
cross-invocation persistence, historical data collection, retention,
longitudinal analytics, repository memory, learned feedback,
RAG/LLM-Wiki-style knowledge storage, user/contributor profiling, or
behavior adaptation from stored review history. Those concerns may make
sense in a future **product** built around the Skill, where storage,
consent, retention, deletion, access control, privacy, and other
product/legal responsibilities can be designed explicitly — but they are
intentionally not implemented in the Skill itself, and this decision does
not replace them with another Skill-level learning or persistence
mechanism. This is intentional scope control, not abandonment of a
useful idea: a Skill performs a bounded action; a product may collect and
retain information across actions; historical analytics and learning
introduce persistence, privacy, retention, deletion, ownership, and
legal/compliance responsibilities the Skill should not own.

This decision does not reduce any *invocation-local* scope already owned
by the Skill, the benchmark system, or #182's telemetry — structured
output or metrics produced and consumed within a single invocation are
unaffected. What is out of scope is the Skill owning historical
collection, storage, or aggregation *across* invocations. It closes §2's
DAG at `(#182 + #329) → Tier 4 complete`, with #131/#130 named only as
out-of-scope product-layer capabilities, never as blocking or
load-bearing work anywhere in §2's DAG, §3's layer set, or §10's rollout
sequence. §2, §2.1, §3, §7, §9, and §10 below are updated to remove
#131/#130 from the active DAG/layer set and to record this boundary; §1,
§4, §5, §6, §8, §11, and §12 are otherwise unaffected.

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
   invoking the packaged `local-code-review` Skill's semantics. The
   original PR-level benchmark check this problem statement was written
   against (`docs/benchmark/ci-integration.md` §4, retired by
   [#420](https://github.com/amirbena/code-review-skill/issues/420))
   already documented that such a runtime is "almost certainly"
   unavailable on a bare GitHub-hosted runner, so that check could
   classify a PR as applicable and still never execute anything —
   historical motivation, kept for record; today's PR-time path is #333's
   classification and #334's Top-K selection instead.
4. **Workflow telemetry and benchmark ground truth are separate concerns
   that need a clear boundary, and analytics/learning are a related
   concern that is explicitly out of the Skill's scope.** #182 and #329's
   benchmark tree each produce review-related signal inside the Skill's
   invocation-scoped boundary, and without an explicit boundary between
   them it is easy to conflate "what the reviewer inspected" with
   "whether the reviewer was correct." #131 (analytics) and #130
   (learning) would have introduced a third and fourth concern — but both
   are closed `not planned` as product-layer capabilities (see the
   addendum above): they require persisted, cross-invocation history that
   crosses the boundary from an invocation-scoped review Skill into a
   stateful product/knowledge layer, so this document does not carry them
   forward as active concerns needing a boundary within the Skill.

The gap this document closes is not a missing feature — it is a missing
**map**. #329's three children (#330/#331/#332) already fan out into eight
further issues, each with its own detailed scope, and #182 (still active)
and #131/#130 (closed `not planned`, kept here for historical reference)
each reference the others informally ("relates to", "distinct from"). Without
one place that fixes the dependency order and the layer boundaries, that
informal cross-referencing drifts: a later issue could re-derive (and
subtly diverge from) an architectural decision another issue already made,
or two issues could silently duplicate a responsibility neither fully owns.
This document is that one place.

## 2. Canonical dependency DAG

```text
#330(+#391) → (#333 → #334 || #338 → #339 → #332) → #335 → #331 → #329 → (#182 + #329) → Tier 4 complete

#336 → #337 : historical evidence only (§2.3) — superseded, not load-bearing above
#131, #130  : product-layer capabilities, closed `not planned` — see the
              Product-layer boundary decision addendum above; no longer
              part of this DAG
```

This is a **practical build/trust order**, not a literal redraw of every
native GitHub `Depends on` / `Blocks` / parent-child edge — those native
edges (recorded on each issue and summarized in §2.1 below) already exist
and are not changed by this document. The DAG above states the order in
which the work actually becomes *usable*, which is stricter than the
native edges in one place worth calling out explicitly (§2.2).

**Revised by #391.** The runtime foundation this DAG threads everything
else through is no longer `#330 → #336 → #337`. #330 (as revised by #391)
now defines two execution classes — see §4 — and #337, Class 1's
provisioning issue, is superseded: no candidate cleared Class 1's
viability bar at an acceptable cost (#336's spike, #366's follow-up), and
further Class 1 pursuit is not planned. #336 and #337 are kept in the DAG
above only as historical evidence, drawn separately and explicitly marked
non-load-bearing, rather than deleted from the record.

Read left to right:

- **#330(+#391)** — the runtime foundation is now the revised contract
  itself, not a provisioned credential: #330 fixes the vendor-neutral
  execution contract (what any runtime in either class must satisfy), and
  #391 adds the two-class split (§4) plus the selected Class 2
  scheduled-integration target (Claude Cloud Routines). Nothing downstream
  needs #337 to land — it needs *some* qualifying runtime, which today
  means a maintainer's own on-demand invocation, and eventually a Cloud
  Routine once a separate implementation issue builds it (§4).
- **`(#333 → #334 || #338 → #339 → #332)`** — two independent branches
  fan out from the runtime foundation and run in parallel:
  - the **PR-time branch**, #333 (canonical taxonomy + inverted index)
    then #334 (deterministic Top-K selector + coverage policy) — see §5;
  - the **nightly branch**, #338 (scheduled full-corpus execution +
    history) then #339 (drift detection + regression issue lifecycle),
    which together constitute #332 — see §6.

  These two branches share no code and no scheduling dependency on each
  other; they are drawn in parallel (`||`) because both only need a
  qualifying runtime to exist (§4), not #337 specifically and not each
  other's output. #339 additionally depends on #338's persisted history
  (an in-branch dependency), and #332 is the tracking parent that both
  children complete. §2.3 records the exact wording each of #331's and
  #332's own children still needs corrected to match this — not yet
  applied.
- **→ #335** — shadow-validation is the join point: it needs #334's
  informational selector *and* #332's nightly history (i.e., #339's
  completed drift-detection loop) as its evidence source, so it cannot
  start meaningfully until both branches have produced real output. #335's
  own scope (promoting the selector to a *required* merge check) needs a
  bounded correction per §2.3 — a required, contributor-blocking gate is
  no longer this architecture's direction (§4).
- **→ #331 → #329** — #331 (the Top-K-gate tracking parent) completes once
  its children do; #331 completing alongside #330 and #332 completing is
  what closes #329 (the whole epic's tracking parent).
- **→ (#182 + #329) → Tier 4 complete** — once #182 (telemetry) and #329
  (a trustworthy benchmark-quality signal) both exist, this DAG's active
  implementation scope is complete. #131 (analytics) and #130 (learning)
  are no longer downstream implementation steps of this DAG: both are
  closed `not planned` as product-layer capabilities — see the
  Product-layer boundary decision addendum above and §7 for the
  rationale that would have gated #131 on #182+#329 and #130 on #131, had
  either been implemented.

### 2.1 Native tracker edges (as recorded on each issue)

| Issue | Parent | Depends on | Blocks / children |
| --- | --- | --- | --- |
| #329 | — | — | children: #330, #331, #332 |
| #330 | #329 | — | blocks #331, #332; children: #336, #337, #391 |
| #391 | #330 | #330 | revises #330's runtime contract; supersedes #337 |
| #336 | #330 | #330 | blocks #337 (historical — see §2.3) |
| #337 | #330 | #330, #336 | superseded by #391 — no longer load-bearing |
| #331 | #329 | #330 | children: #333, #334, #335, #420 |
| #333 | #331 | #330 | blocks #334 |
| #334 | #331 | #333, #330 | blocks #420, #335 |
| #335 | #331 | #334, #332 | — |
| #420 | #331 | #334 | blocks #335 |
| #332 | #329 | #330 | children: #338, #339 |
| #338 | #332 | #330 | blocks #339 |
| #339 | #332 | #338 | — |
| #182 | — | relates #131 | — |
| #131 *(closed `not planned` — product layer)* | — | #44 (open, not in this doc's scope) | — |
| #130 *(closed `not planned` — product layer)* | — | #42, #43 (both delivered) | — |

#131 and #130 are kept in this table for historical reference only — see
the Product-layer boundary decision addendum above. Neither is part of
this document's active DAG or layer set.

### 2.2 Where the practical order is stricter than the native edges

The native edges alone would let #333/#334 (PR-time branch) and #338
(nightly branch) proceed once **#330** merely exists as a documented
contract, since that is the literal `Depends on: #330` recorded on each.
In practice, both branches need a runtime that actually
`check_runtime_available()`-succeeds to produce anything but
`runtime-unavailable`/`insufficient-coverage` placeholder outcomes.
**Revised by #391:** that no longer means #337's deliverable specifically
— #337 is superseded (§2.3) — it means *any* runtime satisfying §4's
contract, which today is a maintainer's own manual/on-demand invocation
of the existing `ReviewerAdapter`, and will eventually include the Class
2 Cloud Routine integration once a separate implementation issue builds
it. This is a sequencing clarification, not a change to any issue's
recorded dependency — #333, #334, and #338 are free to *start* (design,
tests against synthetic data) at any time; they cannot produce a real,
evidence-backed result until a qualifying runtime actually exists to run
against, whichever class it comes from.

### 2.3 Follow-up corrections required in #331/#332/#335/#338/#339 (not applied by #391)

#391's own scope is the canonical architecture rewrite (this document and
`docs/benchmark/runtime-execution-contract.md`) — it deliberately does not
rewrite #331/#332/#335/#338/#339's own issue text. Their current wording
now conflicts with the revised architecture in the specific, bounded ways
below; each is a candidate for its own small, separately-scoped issue
correction once #391 lands, not something to fix by reinterpretation:

- **#331** — its own "Architecture (high level)" diagram currently reads
  "execute those real benchmarks through #330's runtime" and "eventually
  become a required pre-merge gate, after validation." The runtime
  reference needs updating to the revised §4 (no longer implying a single
  provisioned runtime); the "required pre-merge gate" language needs
  reconciling with §4.3's rule that Class 2 execution must never become a
  contributor/merge prerequisite — #331 should state explicitly that any
  future required-gate promotion would have to be backed by a Class 1
  runtime that does not currently exist and is not being pursued, not
  treated as an expected eventual outcome of the current architecture.
- **#332** — its "Problem" section reads "No workflow runs on a
  `schedule:` trigger" (implying GitHub Actions specifically); its
  children (#338/#339) should be re-pointed at Class 2's Cloud Routine
  target rather than an Actions `schedule:` workflow. Its own "Dependency
  order: #330 → #338 → #339" line stays correct in spirit but should note
  #338 now targets a Cloud Routine, not a provisioned CI credential.
- **#335** — its "Responsibility" and "Scope" sections currently target
  "the actual transition to a required, fail-closed merge gate." This
  needs the same correction as #331: promotion to a contributor-blocking
  gate is not this architecture's direction under §4.3, so #335's scope
  should be reframed to either (a) never promote under the current
  Class 2-only model, or (b) stay explicitly conditional on a future,
  separately-decided Class 1 runtime materializing — not an assumed
  eventual step.
- **#338** — its "Scope" section currently specifies "New
  `.github/workflows/benchmark-nightly.yml`: `schedule:` ... using the
  isolated CI runtime from #330." This is the most directly conflicting
  wording in the tree: #338 needs to be re-pointed at a Claude Cloud
  Routine (per #391's `docs/benchmark/runtime-execution-contract.md` §2.2)
  instead of a new GitHub Actions workflow file, and "the isolated CI
  runtime from #330" needs updating to reference the Class 2 contract
  instead.
- **#339** — its current text does not reference #330's runtime directly
  (it consumes #338's persisted history, not the runtime itself), so no
  conflicting wording was found; it should still be reviewed once #338 is
  corrected, since its "Inputs / dependencies" section depends on #338's
  output shape, which may change when #338 is re-pointed at a Routine.

None of these corrections are applied by this revision — they are
recorded here so they can be made as bounded, individually-reviewable
issue corrections after #391 lands, per #391's own scope boundary.

Historical record: #131's dependency on #329 was never a native tracker
edge (#329 does not list #131 as a blocker, and #131's own `Dependencies`
section only names #44). It had been this document's architectural
judgment — reporting "benchmark-derived quality metrics" (part of #131's
formerly-stated scope) would have required a trustworthy benchmark signal
to exist, which is exactly what #329 delivers — but #131 is now closed
`not planned` (see the Product-layer boundary decision addendum above),
so this judgment no longer gates any active implementation work. It is
kept here only so a future reader understands why #131 previously
appeared downstream of #329 in earlier versions of this document.

## 3. Architecture layers

Nine responsibilities, each with exactly one owner. A layer never
re-implements another layer's logic; it consumes the layer(s) below it
through their existing contracts.

| Layer | Responsibility | Owner | Consumes |
| --- | --- | --- | --- |
| **Runtime execution** | Actually invoking the packaged `local-code-review` Skill's real, unmodified semantics — either automatically/repository-triggered (Class 1, untrusted-input, currently unprovisioned) or maintainer-controlled (Class 2: on-demand today, Cloud Routine once a separate implementation issue builds it). | #330+#391 (contract, both classes) — #336/#337 kept as historical Class 1 evidence, no longer load-bearing (§2.3) | Nothing below it — this is the foundation. |
| **Benchmark candidate taxonomy/indexing** | A small, closed, alias-free classification vocabulary for both corpus cases and PR diffs, and a precomputed inverted index for cheap candidate lookup. | #333 | Runtime execution (its one bounded model call — PR-diff classification — runs through §4's runtime contract, either class). |
| **Bounded PR-time benchmark selection** | Turning a narrowed candidate pool into a deterministic, explainable, coverage-bounded Top-K set of cases to actually execute for a given PR. | #334 | Taxonomy/indexing (candidate pool, PR classification); runtime execution (to run the selected cases). |
| **Pre-merge behavioral gating** | Deciding whether/when the PR-time selection becomes a required, fail-closed branch-protection check, and the evidence bar that justifies that promotion — constrained by §4's Class 2 rule that maintainer-controlled execution must never become a contributor/merge prerequisite; any such promotion would require a Class 1 runtime that does not currently exist (§2.3). | #335 | PR-time selection (the thing being validated); nightly history (the broader-evidence comparison source). |
| **Nightly full-corpus execution/history** | Running the entire corpus on a schedule and persisting comparable, interpretable results over time. | #338 | Runtime execution. |
| **Drift detection / regression issue lifecycle** | Comparing persisted nightly runs, deciding what counts as meaningful drift, and managing one deduplicated GitHub issue per regression. | #339 | Nightly history (#338); the existing `regression-report.md`/#55/#56/#57 metrics (reused, not reimplemented). |
| **Review execution telemetry** | Observational record of what a review actually inspected/executed (files, symbols, expansions, runtime validations, partitions, stages) — never decision-affecting. | #182 | Nothing above — it observes the ordinary review process, independent of the benchmark tree. |
| **Analytics / quality exports** *(product layer — not implemented in the Skill)* | Would have been a consolidated, denominator-defined view of workflow-observation metrics (from telemetry) and benchmark-derived quality metrics (from the benchmark tree), kept explicitly separate. | #131 — closed `not planned` | Review execution telemetry (#182); benchmark-derived ground truth (#329's tree, once trustworthy). |
| **Repository-scoped learning** *(product layer — not implemented in the Skill)* | Would have used eligible, explicit accepted/rejected/resolved finding feedback to improve future precision within one repository, with policy always authoritative. | #130 — closed `not planned` | Analytics/measurement foundation (#131); the existing finding-identity/lifecycle model (#42/#43). |

Layers are listed top-to-bottom in dependency order, but note two
independent sub-graphs: **runtime execution → taxonomy/indexing → PR-time
selection → pre-merge gating** is one chain, and **runtime execution →
nightly execution/history → drift detection** is a second, parallel chain
that only rejoins the first at the pre-merge-gating layer (which needs
nightly history as validation evidence, per §2). **Telemetry** is an
independent ninth layer with no dependency on the benchmark tree at all —
it observes live workflow behavior, not benchmark ground truth. The last
two rows, **analytics** and **learning**, are kept in this table only for
architectural completeness — they record where cross-invocation
measurement/learning would have sat in this map had either been
implemented — but neither is: #131 and #130 are closed `not planned` as
product-layer capabilities (see the Product-layer boundary decision
addendum above). This document's seven *active* layers therefore end at
telemetry (#182) and the benchmark tree (#329's children); analytics and
learning are not part of the active dependency chain in §2.

## 4. Runtime contract

The stable architectural rules that #330, as revised by #391, establishes
— restated here at the level a consumer of the runtime (#333's PR-diff
classification call, #334's selected-case execution, #338's nightly
full-corpus execution) needs, without re-litigating
[`../benchmark/runtime-execution-contract.md`](../benchmark/runtime-execution-contract.md)'s
full text. **Revised by #391**: this section now states two execution
classes instead of one, and #337 (Class 1's provisioning) no longer
appears as an active dependency anywhere in this document.

```text
benchmark runner (run_benchmark.py, unchanged)
  → ReviewerAdapter (the existing abstraction boundary — vendor-neutral)
    → compatible agent CLI/runtime  (candidate-specific, swappable)
      → actual Skill (local-code-review, unmodified, unforked)
        → model backend  (candidate-specific, swappable)
```

This chain is shared by both classes below — nothing about it assumes
who or what triggers execution.

### 4.1 Two execution classes

- **Class 1 — automatic / repository-triggered (untrusted input).**
  Execution a repository-controlled workflow triggers automatically — a
  PR, a push, or any other repository event, including a fork PR the
  maintainer did not author. **No maintainer personal machine, session,
  or credentials**: no code path in this class may reach the maintainer's
  personal workstation, filesystem, shell, SSH state, browser/session
  state, or personally-authenticated CLI session, under any trigger. Runs
  on infrastructure dedicated to CI, never a device also used for
  anything else; credentials are purpose-specific, minimally scoped, and
  independently revocable; fork PRs and other untrusted input stay
  separated from any secret-bearing execution path. **Current status: no
  candidate has cleared this class's viability bar at an acceptable cost**
  (#336's spike, #366's follow-up — kept as historical evidence, not
  reopened); #337 (this class's provisioning issue) is superseded, and
  further pursuit of this class is not planned. The rule itself is
  unchanged and remains the reference for any future proposal that does
  try to satisfy it.
- **Class 2 — maintainer-controlled (optional quality observability).**
  Execution the maintainer themselves initiates or schedules — never
  triggered by contributor PR automation or any other repository event.
  No untrusted input reaches this class's execution path, so it does not
  need Class 1's dedicated-infrastructure/independently-revocable-
  credential machinery — it runs with the maintainer's own
  already-authorized credentials and identity. It **must never become
  reachable from contributor PR automation, and must never become a
  required check for a normal contributor PR or merge** — this is
  optional maintainer quality observability, not a prerequisite for
  installing, using, contributing to, or normally merging changes to the
  Skill. The selected scheduled-integration target is **Claude Cloud
  Routines only** — Claude Desktop scheduled tasks are explicitly
  excluded, because reliable periodic benchmark monitoring must not
  depend on the maintainer's workstation being awake or the desktop
  application remaining open. Full detail:
  [`../benchmark/runtime-execution-contract.md`](../benchmark/runtime-execution-contract.md)
  §2.2/§4.3.

### 4.2 Rules that hold regardless of class or which runtime is selected

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
  change, rather than having the two silently confounded. For Class 2,
  neither the SHA nor the model identity is recorded automatically — the
  Routine integration (not yet built) must do so explicitly.
- **Free/near-zero cost is preferred, not sacrificed-for-fidelity
  blindly.** A cheaper candidate that cannot actually invoke the Skill's
  real multi-step, tool-using semantics is not viable regardless of cost;
  among candidates that clear fidelity, cost, latency, reproducibility,
  and operational complexity are all legitimate comparison axes. For
  Class 2, this includes accounting for the maintainer's Claude
  subscription usage and Routine run limits, not just provider metering.

**This document does not hard-code the final Class 1 runtime choice, and
does not itself implement Class 2.** Nothing above commits to Claude
Code, Anthropic's backend, or any other specific vendor as an
architectural requirement for Class 1 — the contract is satisfied by any
runtime that meets these rules, and the *rejected* approaches (Class 1: a
self-hosted runner reusing the maintainer's personal session, a bare
single-shot completion endpoint standing in for the Skill's actual
tool-use loop; Class 2: Claude Desktop scheduled tasks as the
scheduled-integration mechanism) are rejected on these architectural
grounds, not on vendor identity. Class 2's concrete Cloud Routine
integration — profiles, Routine execution, drift confirmation, evidence
persistence, GitHub issue publication — is scoped to a future
implementation issue, not opened by #391.

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
  → real benchmark execution                      (§4's runtime contract — a
                                                     qualifying runtime, not
                                                     specifically #337)
  → informational first                           (#334)
  → required gate only after evidence             (#335 — see note below)
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
- **Promotion to a required gate happens only after shadow validation —
  and is now additionally constrained by §4.1's Class 2 rule.** #334's
  selector ships and runs informationally first. #335 owns the promotion
  mechanism as described (measuring miss rate and over-selection against
  #332's nightly results over a burn-in window), but §4.1 states that
  Class 2 (maintainer-controlled) execution must never become a required
  contributor/merge check. The retired #255 PR-level workflow
  (`benchmark-check.yml`, formerly the candidate for that eventual
  required-branch-protection promotion) no longer exists
  ([#420](https://github.com/amirbena/code-review-skill/issues/420)), and
  under the current architecture (Class 1 unprovisioned, not being
  pursued) there is no other GitHub Actions runtime #335's promotion step
  is currently permitted to promote against — it stays informational
  unless and until a future, separately-decided Class 1 runtime exists.
  #335's own issue text needs a bounded correction to state this
  explicitly (§2.3); this document does not silently reinterpret #335's
  existing wording.

## 6. Scheduled path (sentinel + comprehensive lanes)

Stable principles drawn from #332/#338/#339, refined into **two**
independently-scheduled, independently-baselined lanes by #431 — see
[`../benchmark/corpus/README.md`](../benchmark/corpus/README.md) and
[`../benchmark/nightly-history-and-baseline.md`](../benchmark/nightly-history-and-baseline.md)
§2 for the operational contract. "Nightly" in the rest of this document
and in #338/#339 is the historical name for this scheduled path; it is not
a claim that execution happens every night — the sentinel lane runs every
3 days and the comprehensive lane runs weekly (§2 below), neither daily.
Exact storage implementation and exact drift/noise thresholds remain
#338's and #339's implementation detail, not recorded here.

```text
scheduled trusted execution       (#338/#431, via a Claude Cloud Routine per
                                    §4.1's Class 2 target, or maintainer-
                                    triggered; main only)
  → sentinel lane                 (#431: the 4 fixed canonical cases,
                                    docs/benchmark/corpus/*.yaml, every 3 days)
  → comprehensive lane             (#431: every benchmark-case/v2 fixture in
                                    the corpus tree, derived programmatically,
                                    weekly)
  → persisted comparable history, (#338/#431, keyed by date + commit SHA +
    independently keyed per lane   runtime metadata + lane)
  → baseline/reference comparison, (#338/#431's chosen baseline policy,
    independently keyed per lane   applied per lane — never cross-lane)
  → meaningful drift detection    (#339, reusing regression-report.md/#55/#56/#57
                                    unchanged, run once per lane)
  → deduplicated issue lifecycle  (#339, per lane)
```

**Revised by #391, then #431.** #338's own text still describes this as a
new `.github/workflows/benchmark-nightly.yml` GitHub Actions `schedule:`
workflow using "the isolated CI runtime from #330" — that wording
conflicts with the Class 2 Cloud Routine target above and needs a bounded
correction (§2.3), not applied by this document. #431 additionally split
the single scheduled lane into the sentinel/comprehensive pair above and
gave each its own keyed baseline (`benchmark_history.py`); it did not
reopen or redesign #338's storage mechanics or #339's drift-vs-noise
policy, only parameterized both by lane.

Principles that hold regardless of the exact storage/threshold choices:

- **Never blocks PR or main.** Scheduled execution (either lane) runs on a
  schedule (a Claude Cloud Routine, per §4.1's Class 2 target) against
  `main` (or a maintainer-chosen ref) and never gates a merge or
  deployment, under any outcome. Nothing in this section is reachable from
  GitHub Actions cron.
- **Two lanes, never rotated or merged into one.** The sentinel lane's 4
  cases are permanent and never sampled, rotated, or Top-K'd; the
  comprehensive lane's membership is derived programmatically from the
  corpus tree's `benchmark-case/v2` fixtures, never a hard-coded count.
  The two lanes are not degrees of one schedule — a maintainer configures
  them as two separate Cloud Routine schedules, and when both land on the
  same night (sentinel's 3-day cadence and comprehensive's weekly Friday
  cadence can coincide), both runs are valid and independently baselined;
  this document does not dedupe or merge them.
- **Baseline policy must avoid silent drift ratcheting, per lane.** A
  naive "always compare to yesterday's run" policy lets a small
  degradation become tomorrow's accepted baseline, silently eroding the
  known-good reference over time. #338/#431 evaluate and document an
  explicit, per-lane baseline policy (a deliberately-refreshed pinned
  reference, keyed so sentinel and comprehensive each pin and compare
  against their own baseline) rather than defaulting to the ratcheting
  shape or letting one lane's baseline stand in for the other's.
- **History is benchmark ground truth.** The persisted scheduled-execution
  history is kept structurally separate from #182's execution telemetry
  (and would have been kept separate from #131's workflow-observation
  export, had #131 been implemented rather than closed `not planned`) —
  never mixed into packaged Skill resources or an existing `docs/`
  analytics surface. It is the
  authoritative benchmark-quality record §7's "benchmark ground truth"
  layer refers to, for both lanes.
- **Drift issues are fingerprinted, deduplicated, updateable, and
  resolvable — per lane.** #339 reuses the existing `regression-report.md`
  contract and #55/#56/#57 metrics unchanged; it adds the policy for what
  counts as *meaningful* drift versus noise, a stable fingerprint from
  already-stable identifiers, and full issue lifecycle (open once, comment
  on recurrence, auto-close on resolution, never auto-close over an
  explicit maintainer `keep-open` override). A sentinel-lane candidate is
  only ever compared against the sentinel baseline, and a comprehensive-
  lane candidate only against the comprehensive baseline — #338/#431's
  `corpus_id` identity (distinct by construction between the two lanes)
  backs `compare()`'s existing fail-closed guard against a cross-lane
  comparison, so no new guard code was needed for this.

## 7. Measurement / analytics / learning boundaries

Two capabilities are actively implemented and produce or consume
review-related signal inside the Skill's invocation-scoped boundary; two
more (#131, #130) were designed here but are closed `not planned` as
product-layer capabilities (see the Product-layer boundary decision
addendum above) — kept in the table below only so the boundary rationale
that would have governed them, had they been built, stays on record.

| Capability | Question it answers | Decision-affecting? |
| --- | --- | --- |
| **#182 — execution telemetry** | What did the reviewer actually inspect and execute (files, symbols, repository-intelligence expansions, runtime validations, partitions, stage completion)? | **Never.** Purely observational; cannot influence findings, severity, suppression, or the decision. This is a deliberately different model from the *decision-affecting* coverage concept in `shared/policies/review-stopping-criteria.md` — #182 does not copy or extend that model. |
| **#329's benchmark tree — ground-truth behavioral evaluation** | Did the reviewer behave *correctly* against known cases with known-correct expected findings? | Indirectly, through the gate: once #335 promotes it, an `insufficient-coverage` or `runtime-unavailable` outcome can fail a required merge check. The benchmark *result itself* never edits a live review's findings — it gates merges of Skill changes, a different mechanism from telemetry. |
| **#131 — analytics** *(closed `not planned` — product layer)* | Would have been a consolidated, denominator-defined view of observed workflow behavior over time (from #182) and benchmark-derived quality metrics (from #329's tree), kept explicitly separate. | N/A — not implemented. Analytics would have reported on past behavior without feeding back into any live review; it is recorded here only as the boundary #131 would have had to respect if built as a product-layer capability. |
| **#130 — learning** *(closed `not planned` — product layer)* | Would have asked whether accepted/rejected/resolved reviewer feedback, once eligible and repository-scoped, could improve future review precision. | N/A — not implemented. Had it been built, it would have been bounded so that canonical policy always wins a conflict, a single rejection never suppresses a later legitimate defect, and any material learned influence is auditable and reversible — recorded here as the boundary a future product-layer implementation would need, not as active Skill behavior. |

The boundary statements this document fixes, so a future contributor
cannot casually conflate them:

- **Telemetry ≠ benchmark ground truth.** #182 records what happened
  during a review; #329's tree records whether the reviewer was *right*
  against known-correct cases. A review can have full telemetry coverage
  and still be behaviorally wrong, and a benchmark case can be evaluated
  with no telemetry involved at all. Neither substitutes for the other.
  This is the boundary that stays active and in-Skill regardless of
  #131's `not planned` status.
- **Benchmark ground truth ≠ live workflow analytics.** #329's tree only
  ever runs against the fixed, versioned corpus under
  `docs/benchmark/corpus/`, in CI, never against a real user's PR.
  `docs/benchmark/regression-report.md` already disclaims live-workflow
  analytics for exactly this reason.
- **Analytics ≠ learning (historical rationale, product layer).** Had
  #131 and #130 been implemented, analytics would have reported on past
  behavior in aggregate without changing how any future review runs, and
  learning would have been the only layer allowed to feed a signal back
  into future reviewer behavior — never implicitly through analytics
  exports being read as training signal. Both are closed `not planned`;
  this bullet is kept only so a future product-layer design starts from
  the same boundary rather than re-deriving it.
- **Learned knowledge ≠ canonical policy (historical rationale, product
  layer).** Had #130 been implemented, whatever it learned from
  repository-scoped feedback would never have gained the authority of
  `shared/policies/` or a Skill's own `policies/` — a learned preference
  could inform a future review's phrasing or prioritization but never
  override, suppress, or weaken a canonical policy rule. This remains the
  binding constraint on any future product-layer learning capability, even
  though #130 itself is not being implemented in the Skill.

#329 (the benchmark epic) does not implement or formally sequence #182 —
it only establishes a reliable benchmark-quality signal. #131 and #130 are
closed `not planned` (see the Product-layer boundary decision addendum
above), so the dependency §2 previously drew from #329 (and #182) into
#131 is no longer active implementation guidance; it is kept above only as
the architectural judgment a future product-layer analytics capability
would need to reconstruct.

## 8. Cross-cutting invariants

These hold across every layer in §3, regardless of which issue is being
implemented:

- **No duplicate reviewer/runner/evaluator implementations.** Every layer
  consumes the existing `run_benchmark.py` runner, `ReviewerAdapter`
  boundary, matcher, and metrics (#54/#55/#56/#57) through their existing
  contracts. No issue in this tree builds a second reviewer, a second
  runner, or a second evaluator.
- **No personal-machine automatic-execution path.** Restated from §4.1:
  no code path Class 1 (automatic/repository-triggered execution) adds
  may ever reach the maintainer's personal machine, credentials,
  filesystem, shell, SSH state, or browser/session state, under any
  trigger including fork PRs. This does not extend to Class 2
  (maintainer-controlled execution, §4.1), which runs with the
  maintainer's own already-authorized credentials by design — Class 2 is
  restricted instead by never being reachable from contributor PR
  automation and never becoming a contributor/merge prerequisite, and by
  its selected scheduled-integration target excluding Claude Desktop
  scheduled tasks specifically for their own, separate reason (machine-
  availability dependency, not trust boundary — §4.1).
- **Bounded PR-time cost/runtime.** The PR-time path (§5) always executes
  a small, fixed-ceiling number of cases (#334's Top-K bound), never an
  open-ended or corpus-sized job.
- **No full corpus in the merge critical path.** Full-corpus execution is
  exclusively #338's nightly job; nothing on the PR-time path scans or
  executes the entire corpus.
- **Nightly is non-blocking.** Restated from §6: the nightly workflow
  never gates a PR merge or a deployment to `main`, under any outcome.
- **Benchmark history separated from ordinary workflow telemetry.**
  #338's persisted nightly history and #182's execution telemetry are two
  structurally distinct artifacts/storage locations — never merged into
  one, never cross-written by another layer's code path. (This invariant
  would also have applied to #131's analytics export, had #131 been
  implemented; it is closed `not planned` instead.)
- **Canonical policy remains authoritative over learned behavior
  (historical, product layer).** Restated from §7: had #130's learning
  layer been implemented, it could never have acquired the authority of a
  canonical policy file — the same constraint that binds any future
  product-layer learning capability, even though #130 itself is not being
  implemented in the Skill.
- **Issues own execution slices; this design doc owns cross-component
  architecture.** Each of the twelve actively-implemented issues in scope
  retains its own local problem statement, implementation scope,
  acceptance criteria, and non-goals. This document never redefines those
  locally-owned details; it only fixes the order, the boundaries, and the
  invariants between them. If implementation reveals a genuine
  architectural contradiction or a missing invariant, the fix is a
  reviewed change to this document, not a local reinterpretation inside a
  single issue.

## 9. Non-goals

- **No implementation.** This document ships no runtime, selector, or
  nightly workflow. It is architecture and documentation normalization
  only; every concrete behavior is implemented and validated by its
  owning issue. (No analytics export or learning behavior is planned at
  all — #131 and #130 are closed `not planned` as product-layer
  capabilities.)
- **No scoring constants, thresholds, or storage schemas.** Exact
  relevance weights, coverage percentages, Top-K bounds, drift tolerances,
  baseline-refresh cadence, and storage formats are implementation
  decisions that live in #333/#334/#335/#338/#339, not architectural
  commitments recorded here.
- **No runtime/vendor selection, and no Class 2 implementation.** §4
  fixes the contract every candidate must satisfy in either class. For
  Class 1, #336/#366 already evaluated concrete candidates (historical
  evidence, §2.3) and no winner cleared the bar; #337 (provisioning) is
  superseded and not being pursued further. For Class 2, §4.1 names
  Claude Cloud Routines as the selected scheduled-integration *target*,
  but this document does not implement that integration — profiles,
  Routine execution, drift confirmation, evidence persistence, and
  GitHub issue publication are scoped to a future implementation issue.
- **No reassignment of tracker metadata.** This document changes no
  issue's assignee, label, native parent/sub-issue relationship,
  dependency edge, or state. §7's historical #131-depends-on-#329/#182
  judgment is recorded as architectural context for why #131 previously
  appeared downstream of #329/#182 in this document's DAG; it is not a
  native tracker edge and is no longer active guidance now that #131 is
  closed `not planned` (see §2.2). The `not planned` closure of #130 and
  #131 themselves is recorded directly on each issue via a GitHub `not
  planned` close, not by this document reassigning tracker metadata on
  their behalf.

## 10. Smallest useful first implementation

1. **This model** — the dependency DAG (§2), the nine architecture layers
   and their single owners (§3, two of which — analytics and learning —
   are closed `not planned` product-layer capabilities kept only for
   completeness), the vendor-neutral runtime contract (§4), the PR-time
   and nightly path principles (§5, §6), and the telemetry/benchmark
   boundary (§7) — consumed as the canonical reference every one of the
   **twelve actively-implemented issues** points back to (#131 and #130
   are excluded; see the Product-layer boundary decision addendum above).
2. **A compact "Canonical design" section on each of the twelve active
   issues**, naming this document and the issue's own local
   responsibility and relevant sections, so implementation work starts
   from this shared map rather than re-deriving it per issue.
3. **Conservative compression of duplicated architectural prose** in the
   issues, where this document already states it canonically — while
   preserving every issue's local problem statement, scope, dependencies,
   and acceptance criteria untouched.

**Deferred** (named here so scope stays fixed):

- any actual runtime, selector, workflow, taxonomy, index, storage, or
  drift-detection implementation — all of #330–#339 and #182's own scope,
  unchanged by this document. Analytics and learning (#131, #130) are
  **not** deferred — they are closed `not planned` as product-layer
  capabilities (see the addendum above) and are excluded from this list
  entirely, not merely postponed;
- picking a winning runtime candidate (#336's empirical spike);
- setting concrete scoring/coverage/drift thresholds (each owning issue's
  own decision, informed by its own burn-in/validation data).

## 11. Relationship to existing canonical policies and docs

- [`../benchmark/README.md`](../benchmark/README.md) owns the benchmark
  contracts this architecture sits above: fixture format, corpus, runner
  contract, match criteria, the three quality metrics, and the
  informational PR-time taxonomy/selection wiring (`taxonomy.md` #333,
  `selection.md` #334 — the earlier standalone CI wiring, `ci-integration.md`
  #255, was retired by #420). This document adds the
  runtime/selection/nightly/measurement architecture on top; it does not
  redefine any of those contracts.
- [`../finding-confidence/README.md`](../finding-confidence/finding-confidence-model.md)
  owns the finding `confidence` field that runtime-validated and
  benchmark-derived evidence roll into; unrelated to this document's
  scope beyond both ultimately informing review-quality signal.
- `shared/policies/review-stopping-criteria.md` owns the
  *decision-affecting* coverage concept that #182's telemetry is
  explicitly distinct from (§7).
- `docs/benchmark/regression-report.md` owns the run-to-run comparison
  contract #339 reuses unchanged (§6), and already disclaims
  live-workflow analytics — a disclaimer #131 would have had to keep
  intact had it been implemented; #131 is closed `not planned` instead.
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
  concludes. The concluded research record is
  [`verdict-consistency-boundary-research.md`](verdict-consistency-boundary-research.md):
  build an MVP now against the existing fixed-vocabulary decision/severity
  markers (never wait on #67/#71), reconcile pre-publish at four call
  sites across both Skills' runbooks (never post-publish), and
  withhold-and-report on a detected mismatch (never self-correct). A
  follow-on implementation issue is outlined there, not yet filed.

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
