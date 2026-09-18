# Benchmark/Evaluation Ownership Boundary Checkpoint

Repository-development decision record for issue
[#425](https://github.com/amirbena/code-review-skill/issues/425), blocked
by [#329](https://github.com/amirbena/code-review-skill/issues/329) (Tier 4
operational benchmark-quality loop epic) and
[#412](https://github.com/amirbena/code-review-skill/issues/412) (Tier 5
capability/progressive-loading reassessment checkpoint). Per #425's own
Non-Goals ("No implementation in this issue — this issue defines scope and
scheduling only") and Validation ("Reviewed and approved by a maintainer
before any child implementation issue is opened"), this record defines the
ownership boundary and the scheduling decision only. It does not move a
file, does not rewrite corpus content, does not redesign the taxonomy or
selector, and does not open the relocation issue itself.

Like the rest of [`./`](README.md), this is a repository-development doc:
**not** packaged into either Skill archive, and no packaged Skill resource
depends on it. It applies
[`capability-architecture-model.md`](capability-architecture-model.md) §H
(benchmark architecture) and §E.2 (recommended topology) without
re-deriving their evidence.

## 1. Are both prerequisites actually satisfied?

Yes, both closed one day before this record:

| Issue | Role | State |
| --- | --- | --- |
| [#329](https://github.com/amirbena/code-review-skill/issues/329) | Tier 4 operational benchmark-quality loop epic (3/3 sub-issues #330–#332 complete) | Closed 2026-09-17 |
| [#412](https://github.com/amirbena/code-review-skill/issues/412) | Tier 5 checkpoint, itself a child of epic [#403](https://github.com/amirbena/code-review-skill/issues/403) (also closed) | Closed 2026-09-17 |

#412's recorded decision
([`specialist-depth-continuation-checkpoint.md`](specialist-depth-continuation-checkpoint.md)
§8) is "continue the pattern for exactly one more capability (`scale`), not
a batch, and not yet with generated routing." That answers #425's
precondition — the capability/progressive-loading architecture has
stabilized enough to define a boundary against, even though the broader
thirteen-capability migration (§M.4) remains far from complete. #425 does
not depend on that full migration finishing; it depends only on #412's
checkpoint existing, which it now does.

**Both blocking conditions are satisfied. #425's boundary work may proceed;
per §8 below, its child implementation issue may also now be opened.**

## 2. What #425 is actually inventorying

Everything under `docs/benchmark/` today (per
[`docs/benchmark/README.md`](../benchmark/README.md)'s own document map),
plus its `scripts/benchmark/` and `tests/reference/benchmark/` counterparts:

| Class | Assets |
| --- | --- |
| Corpus data | `docs/benchmark/corpus/` (4 root `benchmark-case/v2` fixtures + per-domain subdirectories), `docs/benchmark/corpus-index.json` |
| Contract documents | `fixture-format.md`, `taxonomy.md`, `selection.md`, `runner-contract.md`, `regression-report.md`, `match-criteria.md`, `missed-and-incorrect-findings.md`, `severity-accuracy.md`, `duplicate-noise.md`, `runtime-execution-contract.md`, `nightly-history-and-baseline.md`, `drift-detection-and-regression-lifecycle.md`, `cloud-routine-integration.md` |
| Research / historical records | `claim-correspondence-adequacy.md`, `runtime-candidate-decision.md` |
| Reference example sets (non-CI-gated) | `senior-voice-examples.md`, `reviewer-brief-examples.md`, `examples/` |
| Navigation | `docs/benchmark/README.md` |
| Harness code | `scripts/benchmark/*.py` (11 files: `run_benchmark.py`, `benchmark_review_adapter.py`, `select_benchmark_cases.py`, `build_benchmark_index.py`, `benchmark_corpus_membership.py`, `benchmark_drift.py`, `benchmark_history.py`, `run_benchmark_routine.py`, `benchmark_routine_verify.py`, `classify_pr_diff.py`, `shadow_validate.py`) |
| Reference models (test-only) | `tests/reference/benchmark/*.py` (18 files) |

One correction to #425's Scope text: it names
`scripts/benchmark/benchmark_ci_classifier.py` and its `docs/benchmark/`
path allowlist as needing a coordinated update. That file no longer
exists — the PR-level CI check it powered was already retired
([#420](https://github.com/amirbena/code-review-skill/issues/420),
recorded in `docs/benchmark/README.md`, "Retired: PR-level benchmark CI
check"), and its PR-time responsibility moved to `taxonomy.md` (#333) and
`selection.md` (#334). A future relocation issue has one fewer coordinated
reference to update than #425 assumed.

## 3. The ownership boundary

**None of `docs/benchmark/`'s contents are generic, human-facing
documentation in the sense `docs/` is supposed to hold.** Every asset in
§2 exists to define or exercise the behavior of code — a fixture schema, a
scoring algorithm, a runner's isolation guarantee, a scheduled job's
storage shape — not to explain the system to a reader who isn't extending
it. `capability-architecture-model.md` §H.1 already gives the structural
evidence for treating this as an evaluation subsystem rather than prose:

- Corpus directory names already match capability names one-to-one
  (§H.3's assignment table maps its ~180 cases across 23 entries — root
  plus 22 named corpora — to a named capability or router boundary; the
  `docs/benchmark/corpus/` directory itself has since grown to 26
  subdirectories, so §H.3's own table already lags the current corpus set
  by several entries, e.g. `candidate-finding-validation`,
  `decision-derivation`, `finding-placement`).
- Corpus and policy have independent lifecycles — 0-of-7 commit-set
  overlap for 6 of 7 sampled capabilities (§H.1) — so corpus is not
  incidental prose next to the policy it tests, it is a co-owned artifact
  with its own change cadence.
- Corpus is welded to `tests/`, not to `shared/`: 31 of 31 corpus commits
  also touch `tests/` (§H.1). A relocation that moves corpus without its
  tests would break that weld; the two must move together.

The boundary this record adopts, applying §E.2's target shape without
committing to its full directory restructure (§4 below explains why):

| Class (§2) | Boundary | Rationale |
| --- | --- | --- |
| Corpus data | Benchmark/evaluation infrastructure — capability-owned, not `docs/`-owned | §H.1's structural evidence above; §E.2 places it at `capabilities/<name>/corpus/`, adjacent to the capability it tests |
| Contract documents | Benchmark/evaluation infrastructure — a machine contract with a human-readable description, the same relationship `shared/policies/*.md` has to reviewer behavior | Each one is cited by name from a `capability.yaml` `benchmark:` field (§5) or from a reference model in `tests/reference/benchmark/`; none stands alone as reader-facing prose independent of the code it constrains |
| Research / historical records | Benchmark/evaluation infrastructure, but of the *design-record* kind already established elsewhere in this repository (this document's own family) | `claim-correspondence-adequacy.md` and `runtime-candidate-decision.md` already self-identify as "research record, not a contract change" — they belong with other capability/benchmark design records, not with generic docs |
| Reference example sets | Benchmark/evaluation infrastructure (non-CI-gated corpus, per `docs/benchmark/README.md`'s own framing) | Same corpus-adjacent lifecycle as fixtures; only their non-gating status differs |
| Navigation (`README.md`) | Moves with the subsystem it indexes | A document map has no independent purpose once its subject relocates |
| Harness code (`scripts/benchmark/`) | Already infrastructure, never `docs/`-classified — unaffected in kind, only in location | Matches §E.2's `runtime_platform/benchmark/` |
| Reference models (`tests/reference/benchmark/`) | Already `tests/`-classified — unaffected in kind or location by this record | §H.1's "welded to tests" finding; H.5's "no duplicate reviewer/runner/evaluator implementations" invariant governs this tier, not this record |

**Net boundary statement:** `docs/` ownership should be limited to
material that explains the system to a reader — design records,
architecture maps, threat models, feature documentation — and the
benchmark/evaluation subsystem, in its entirety, is not that. It is
infrastructure that currently lives under `docs/` only because it is
Markdown/YAML/JSON, which #425's Problem statement already identified as
the misclassification. This record does not, however, mean every file in
§2 changes address (§4).

## 4. Why this boundary decision does not yet commit to a directory move

`capability-architecture-model.md`'s own README states its target
topology, including §E.2's `runtime_platform/benchmark/` and
`capabilities/<name>/corpus/`, is "a research recommendation, not a
contract change... no file has moved, no repository has been created, no
policy's canonical ownership has changed." As of this record:

- `capabilities/<name>/capability.yaml` manifests exist for 13
  capabilities (build-time declarations only, per §E.2's "unchanged
  either way" note on `capability.yaml`), each already carrying a
  `benchmark:` field — see §5.
- `runtime_platform/` and `adapters/` — the two other top-level
  directories §E.2's topology requires — **do not exist yet.** Only the
  manifest layer of the broader capability-architecture migration has
  landed; the router/kernel separation (§C, rated highest-risk in §J.2
  Step 5) and the adapter-thinning step (§E.2's `adapters/`) have not
  been attempted.

Relocating `docs/benchmark/` into a `runtime_platform/benchmark/` that does not
exist, and a per-capability `corpus/` structure whose sibling
`capabilities/<name>/` directories today hold only a manifest file each,
would build the target topology's benchmark half before its structural
prerequisites exist elsewhere in the repository. That inverts #425's own
scheduling rationale — "after both prerequisites close" was meant to
ensure the boundary is defined *correctly*, not to trigger an immediate
move regardless of what else has or hasn't been built. **Defining the
boundary and scheduling its relocation are the two things this record
does; performing the relocation is not.**

## 5. What any future relocation issue must not break

Recorded now so the future child issue inherits a complete list rather
than rediscovering it:

- Nine `capability.yaml` files already declare a `benchmark:` field
  pointing at `docs/benchmark/corpus/<name>` paths (`conditional-passes`,
  `authorization-github`, `finding-placement-derivation`,
  `publication-github`, `parallel-execution`, `runtime-execution`, `scale`
  — which lists two paths, also including `docs/benchmark/scale-
  progressive-loading-proof` — `reviewer-assist`, `specialist-depth`).
  Four others (`context-resolution`, `remediation`, `repository-checkout`,
  `stateful-review`) point at `tests/reference/review/*.py` instead and are
  out of this boundary's scope entirely — they were never under
  `docs/benchmark/`. That accounts for all 13 existing `capability.yaml`
  manifests.
- `docs/ARCHITECTURE.md`'s "Code-review quality benchmark" and
  "Denied-capability security-event benchmark" sections link every
  `docs/benchmark/*` document by relative path.
- `docs/benchmark-measurement-architecture/README.md` cross-references
  `docs/benchmark/` as the corpus/harness layer under its nine-layer model
  (§H.5 — that record is authoritative and unchanged by this one).
- Every `tests/unit/benchmark/test_*.py` file imports its matching
  `tests/reference/benchmark/*.py` reference model and, for corpus tests,
  reads `docs/benchmark/corpus/` by path.
- `scripts/benchmark/build_benchmark_index.py` and
  `benchmark_corpus_membership.py` read `docs/benchmark/corpus/` to build
  `corpus-index.json`.

None of this is exhaustive verification (that is the future issue's job,
per #425's own Acceptance Criteria "No broken links, imports, scripts,
tests, or CI references after any move"); it is the reference-inventory
starting point.

## 6. Wiki carry-forward

#425's Problem statement flags that the project Wiki already documents
benchmark/evaluation architecture against the pre-relocation structure,
and its Acceptance Criteria requires relevant pages be updated "with no
stale guidance." Per #425's own Non-Goals ("No general Wiki rewrite —
only benchmark/evaluation Wiki pages actually affected by this issue's
architectural changes are in scope"), no Wiki page is edited by this
record, since this record makes no path change. The future relocation
issue must audit and update Wiki pages describing `docs/benchmark/`
structure, corpus paths, or ownership as part of its own change, not as a
separate follow-up.

## 7. Decision

**The ownership boundary is: the entire benchmark/evaluation subsystem
(§2) is infrastructure, not generic documentation, and none of it should
be reclassified as staying under `docs/` on the merits of its content.**
Relocation should follow `capability-architecture-model.md` §E.2's target
shape (`runtime_platform/benchmark/` for harness/contracts,
`capabilities/<name>/corpus/` for per-capability corpus) rather than any
new topology, per #425's own Scope constraint. (§E.2's top-level
directory was `platform/` at the time this record was written; #458
renamed it to `runtime_platform/` — see §E.2.1 — to avoid shadowing
Python's stdlib `platform` module. This item is updated to the resolved
name.)

**Scheduling: both prerequisites are closed (§1), so #425's own
precondition for opening a child implementation issue is met — but that
child issue should be scoped to what §4 shows is actually buildable
today, not to the full §E.2 topology.** Concretely, the future issue(s)
should:

1. Not attempt the corpus move until enough of `capabilities/<name>/`
   exists as more than a manifest — i.e., sequence behind whichever
   capability-body extraction issue (§L7–L10 in
   `capability-architecture-model.md`) is active for a given capability,
   rather than moving all ~180 cases in one batch. This mirrors #412's own
   §8 "one capability at a time, not a batch" reasoning and avoids
   repeating, at the corpus layer, the exact batching risk #412 was
   created to avoid at the capability-extraction layer.
2. Move the contract documents and harness code
   (`scripts/benchmark/`, `tests/reference/benchmark/`) to a
   `runtime_platform/benchmark/` location independently of the per-capability
   corpus split, since §E.2 places them together but they have no
   structural dependency on `capabilities/<name>/` existing first — this
   piece could proceed without waiting on further capability-body
   extractions.
3. Treat `docs/benchmark/README.md` and the research/historical records
   (`claim-correspondence-adequacy.md`, `runtime-candidate-decision.md`)
   as moving with whichever of (1) or (2) becomes their new canonical
   home, not as a third independent move.
4. Update every reference in §5, plus the Wiki pages named in §6, in the
   same change that performs the move — not as a follow-up.
5. Preserve `docs/benchmark-measurement-architecture/`'s existing
   authority (§H.5) unchanged; this boundary is about `docs/benchmark/`'s
   classification, not about reopening the measurement-architecture
   layers above it.

This decision does not itself open that child issue — per #425's Non-Goals,
that remains future work, and per #425's Validation, this record is the
maintainer review step that precedes it.

## 8. Out of scope

- Opening the relocation child issue(s) itself (#425 Non-Goals).
- Any taxonomy semantics change, selector redesign, threshold/evidence-bar
  recalibration, or corpus content rewrite (#425 Non-Goals, all explicit).
- Fixing `run_benchmark.py`'s non-recursive `glob` (§H.4's "4 of ~180 cases
  execute" problem) or the `benchmark_review_adapter.py` rendering
  coupling (§H.4) — both flagged in the model as separate issues (L12, the
  #67 schema), not this boundary decision.
- Re-litigating #412's specialist-depth-pattern-continuation decision or
  #329's benchmark-quality-loop closure — both are cited, not re-run.
- Designing `runtime_platform/`'s or `adapters/`'s full directory contents beyond
  the benchmark subsystem — this record scopes only the benchmark/
  evaluation boundary #425 asked for.

## Related

- [#425](https://github.com/amirbena/code-review-skill/issues/425) — the
  issue this record answers.
- [#329](https://github.com/amirbena/code-review-skill/issues/329),
  [#412](https://github.com/amirbena/code-review-skill/issues/412) — the
  two closed prerequisites verified in §1.
- [`capability-architecture-model.md`](capability-architecture-model.md)
  §E.2 (recommended topology), §H (benchmark architecture, all five
  subsections), §L "Benchmark migration" (L11–L14) — the design record
  this checkpoint applies without re-deriving.
- [`specialist-depth-continuation-checkpoint.md`](specialist-depth-continuation-checkpoint.md)
  (#412) — the sibling checkpoint whose "one capability at a time"
  reasoning §7 above extends to the corpus-relocation sequencing.
- [`../benchmark/README.md`](../benchmark/README.md) — the document map
  this record inventories in §2 without modifying.
- [`../benchmark-measurement-architecture/README.md`](../benchmark-measurement-architecture/README.md)
  — the authoritative, unchanged measurement-architecture layer this
  record's boundary sits underneath (§H.5).
