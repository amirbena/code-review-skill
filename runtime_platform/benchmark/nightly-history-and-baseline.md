# Nightly Full-Corpus Execution and History

Repository-development contract for GitHub Issue
[#338](https://github.com/amirbena/code-review-skill/issues/338), part of
the nightly branch
(`docs/benchmark-measurement-architecture/benchmark-measurement-architecture-model.md`
§6) that runs in parallel with the PR-time branch
([#333](https://github.com/amirbena/code-review-skill/issues/333)/[#334](https://github.com/amirbena/code-review-skill/issues/334)).
Parent: [#332](https://github.com/amirbena/code-review-skill/issues/332).
Blocks [#339](https://github.com/amirbena/code-review-skill/issues/339)
(drift detection and the GitHub regression-issue lifecycle), which needs
this document's persisted, baseline-comparable history as its input.

Like the rest of [`./`](README.md), this is a **repository-development
doc: not packaged into either Skill archive**, and no packaged Skill
resource depends on it.

This document builds the **vehicle #415 already shipped**
([`cloud-routine-integration.md`](../../docs/benchmark/cloud-routine-integration.md),
`runtime_platform/benchmark/scripts/run_benchmark_routine.py`) into a **scheduling policy,
a durable history store, and an explicit baseline policy**. It does not
redefine #415's own execution/verification/evidence-issue mechanics, and
it owns none of #339's drift-vs-noise classification or GitHub issue
lifecycle (Non-goals, below).

## 1. Scope

- The scheduling policy and full-corpus invocation choice for a Claude
  Cloud Routine run (§2).
- Persisted, comparable history keyed by date and commit SHA, plus the
  runtime/model/Skill metadata needed to interpret a result later (§3).
- Storage location and retention policy, structurally separate from
  [#182](https://github.com/amirbena/code-review-skill/issues/182)'s
  execution telemetry (§3, §5). (It would also have been kept separate
  from [#131](https://github.com/amirbena/code-review-skill/issues/131)'s
  workflow-observation export, had #131 been implemented rather than
  closed `not planned` as a product-layer capability.)
- First-run/bootstrap behavior (§4).
- The baseline policy, and how it avoids silently ratcheting a
  degradation into tomorrow's accepted reference (§4).

## Non-goals

- Drift-vs-noise classification, fingerprinting, or GitHub regression
  issue open/update/resolve lifecycle — [#339](https://github.com/amirbena/code-review-skill/issues/339)
  owns all of it, consuming this document's history/baseline as input.
- The Cloud Routine's own checkout/SHA-pinning/completion-verification/
  evidence-persistence/credential-bounding mechanics —
  [#415](https://github.com/amirbena/code-review-skill/issues/415)/
  [`cloud-routine-integration.md`](../../docs/benchmark/cloud-routine-integration.md) own all
  of it, unchanged.
- Re-deriving match/metrics logic already owned by
  [#54](https://github.com/amirbena/code-review-skill/issues/54)/[#55](https://github.com/amirbena/code-review-skill/issues/55)/[#56](https://github.com/amirbena/code-review-skill/issues/56)/[#57](https://github.com/amirbena/code-review-skill/issues/57).
- Any PR-blocking behavior, or a GitHub Actions `schedule:` workflow —
  superseded by [#391](https://github.com/amirbena/code-review-skill/issues/391),
  not reopened here.

## 2. Scheduling policy

**Two-tier scheduling (#431).** A maintainer configures **two** Claude
Cloud Routines (`cloud-routine-integration.md` §9.1), not one:

| Lane | `--mode` | Recurrence | Corpus |
| --- | --- | --- | --- |
| Sentinel | `sentinel` (deprecated alias: `full`) | every 3 days | the 4 permanent canonical cases (`--corpus-dir`'s own top-level, non-recursive glob) |
| Comprehensive | `comprehensive` | weekly, Friday night | every `benchmark-case/v2` fixture in the corpus tree, discovered programmatically |

Both target a **01:00 Israel-local start / 04:00 maximum-completion**
window; each also supports the same Routine's manual/on-demand trigger for
an off-schedule run. Timezone/DST handling for that window is a **Cloud
Routine scheduling-configuration responsibility, never repository runtime
logic** — the schedule itself is set in Israel local time (or UTC with the
correct seasonal offset) in the Routine's own product surface;
`runtime_platform/benchmark/scripts/` computes no timezone. This document does not fix a
specific cron expression beyond that recurrence/window: `cloud-routine-
integration.md` §7 already assigns sizing run frequency against Claude
subscription usage and Routine run limits to the maintainer, and the
comprehensive lane (~89 fixtures) is far more expensive per run than
sentinel's 4 cases — which is why it runs weekly rather than every 3 days.

**Collision is expected and independently baselined, not deduplicated.**
Every 3 days and weekly periodically coincide; when they do, both Routine
runs execute, verify, and persist independently, each against its own
keyed history/baseline (§3–§4). Deduplicating a same-night collision is
out of scope for this document.

The Routine prompt template (`cloud-routine-integration.md` §9) is
extended with one additional step for each lane, after that lane's
existing verified evidence-issue post:

```text
3. Run (sentinel lane shown; comprehensive lane is identical except
   --mode comprehensive and its own --evidence-issue thread):
   python3 runtime_platform/benchmark/scripts/run_benchmark_routine.py \
     --mode sentinel \
     --evidence-issue <sentinel tracking issue number> \
     --model-id <the model backend this Routine session is running as> \
     --results-out /tmp/benchmark-sentinel-results.json
4. If step 3 exited non-zero, stop (per cloud-routine-integration.md §9
   step 4) — do not run step 5.
5. Only on a step-3 success, persist history:
   a. Fetch and check out the `benchmark-history` branch into a
      dedicated local directory (creating an empty orphan branch the
      first time it does not exist).
   b. python3 runtime_platform/benchmark/scripts/benchmark_history.py record \
        --history-root <that directory> \
        --results-file /tmp/benchmark-sentinel-results.json \
        --routine-metadata-file <the JSON `run_benchmark_routine.py` printed
          to stdout in step 3 — its top-level `metadata` block>
      (`--lane` defaults to the run's own `mode`, canonicalized — no
      separate flag is normally needed; see §3.2/§4.)
   c. Commit and push the `benchmark-history` branch. Never open a PR for
      this — it is Class 2 evidence storage, not reviewable Skill source.
```

`run_benchmark_routine.py --results-out PATH` (added by #338, additive and
backward compatible — every existing call site that omits it is
unaffected) writes the concatenated raw per-invocation `run_benchmark.py`
output only when the run passed positive completion verification,
mirroring the vehicle's existing fail-closed rule for evidence-issue
posting: an unverified run persists nothing, in either place. For
`--mode comprehensive`, this is the concatenation of one
`run_benchmark.py` invocation per discovered fixture (`cloud-routine-
integration.md` §2.1) — unchanged shape, just more invocations.

**Never blocks PR or `main`.** Nothing above is invoked by
`.github/workflows/**` or any other repository-triggered automation —
there is no independent GitHub Actions benchmark execution path left over
from the retired #255 workflow
([#420](https://github.com/amirbena/code-review-skill/issues/420)) for it
to couple to — the same non-reachability guarantee
`cloud-routine-integration.md` §8 states for the vehicle itself.
No contributor needs benchmark credentials, a Routine, or `benchmark-history`
branch push access for a normal PR or merge.

## 3. Persisted history

### 3.1 Storage location

A dedicated **`benchmark-history`** branch — not `main`, not packaged
Skill resources, not an existing `docs/` analytics surface, and distinct
from #182's execution telemetry (#131's workflow-observation export does
not exist — #131 is closed `not planned` as a product-layer capability;
§6 of the cross-component architecture model). A branch, not a release
artifact, was chosen because it is inspectable with ordinary `git`/GitHub
tooling, needs no separate retention configuration, and keeps evidence
inside the same repository #339 already has push/issue access to.

Layout on that branch (default/sentinel lane paths unchanged since before
#431; a non-default lane gets its own sibling directory/file — §3.2, §4):

```text
history/<date>-<repo_sha[:12]>.json              # sentinel lane (default; unchanged path)
baseline.json                                     # sentinel lane's pinned baseline (§4)

history-comprehensive/<date>-<repo_sha[:12]>.json # comprehensive lane (#431)
baseline-comprehensive.json                       # comprehensive lane's pinned baseline (§4)
```

### 3.2 History entry shape

`runtime_platform/benchmark/scripts/benchmark_history.py`'s `HistoryEntry`:

```json
{
  "date": "2026-09-17",
  "repo_sha": "<full checked-out SHA>",
  "corpus_id": "<sha256 digest of every corpus fixture id + content, lane-specific — see below>",
  "adapter_id": "<reviewer/Skill revision identifier; defaults to repo_sha>",
  "recorded_at": "<UTC ISO-8601, when this script wrote the entry>",
  "routine_metadata": { "mode": "sentinel", "repo_sha": "...", "runtime_name": "...", "runtime_version": "...", "model_id": "...", "timestamp": "..." },
  "results": [ /* runner-contract.md §6 per-case result, verbatim, one per corpus case */ ],
  "lane": "sentinel"
}
```

**Keyed/named baseline identity (#431).** `lane` (`"sentinel"` or
`"comprehensive"`) is the smallest addition that lets each scheduled lane
maintain and compare against its own baseline: it is derived from — not a
replacement for — `routine_metadata.mode`, canonicalized so the deprecated
`full` alias always records `"sentinel"`
(`benchmark_corpus_membership.canonical_lane`). No new identity concept
was introduced beyond this one field; `corpus_id`, `repo_sha`, and
`adapter_id` keep their pre-#431 meaning and shape. `corpus_id` itself is
lane-specific: the sentinel lane keeps the pre-#431 digest (every
top-level `*.yaml` id + content, non-recursive); the comprehensive lane
digests the recursively-discovered `benchmark-case/v2` membership instead
(`benchmark_history.py::comprehensive_corpus_digest`). Because
comprehensive's membership is a strict superset of sentinel's (the 4
top-level cases plus every sub-corpus fixture), the two `corpus_id`
values are never equal for the same corpus tree — which is exactly what
lets `regression-report.md`'s existing `compare()` fail-closed guard
(`runtime_platform/benchmark/reference/benchmark_report.py::compare`) reject a
sentinel-vs-comprehensive cross-comparison automatically, with no new
guard code required.

`corpus_id` mirrors `regression-report.md` §2's definition exactly (a
digest that changes when a fixture changes, so a stale comparison is
detected rather than silently accepted) and is computed the same way the
test-only reference implementation
(`runtime_platform/benchmark/reference/benchmark_report.py::corpus_digest`) computes
it, so a later #339 comparison and this document's persisted `corpus_id`
values are directly comparable. `results` is deliberately the runner's
own per-case shape, verbatim — this document never recomputes or
reinterprets a result, only stores it (§4.3 of the architecture model's
runtime contract: "actual Skill semantics, not a second reviewer
implementation" applies equally to the storage layer).

`record` re-validates that every case's `status` is `executed` before
persisting anything, even though the vehicle's own fail-closed
verification (`cloud-routine-integration.md` §3) should already guarantee
that on the normal path — `record` is a general CLI that can be pointed
at any file, and a corrupted or partial run must never silently become a
persisted history entry or, worse, the bootstrap baseline (§4). This
mirrors `regression-report.md` §2's `BaselineArtifact.from_run`, which
applies the same guard before allowing a promotion.

### 3.3 Retention / rotation

Keep the newest **90** raw history entries **per lane** (`--retention`,
overridable); older entries are pruned automatically as part of `record`,
scoped to that entry's own lane directory (§3.1) — a comprehensive record
never prunes a sentinel entry, or counts against sentinel's retention
budget, and vice versa. Each lane's history entry backing its own current
pinned baseline is never pruned, regardless of age, so a promoted baseline
can never disappear out from under #339's comparisons. At one JSON file
per run holding a corpus's per-case results, 90 entries plus one pinned
baseline per lane is a near-zero, bounded storage cost on a public
repository — the retention window is a maintainer-tunable knob, not a hard
architectural limit.

## 4. Baseline policy

**Chosen policy: a pinned reference baseline per lane, refreshed only by
an explicit maintainer action — never automatically on every scheduled
run.** Sentinel and comprehensive each maintain their own baseline
artifact, independently; nothing here lets one lane's baseline stand in
for the other's.

- `baseline.json` (sentinel; unchanged path) and `baseline-comprehensive.json`
  (comprehensive, #431) each hold one baseline artifact at a time, in
  `regression-report.md` §2's shape (`results`, `corpus_id`, `adapter_id`,
  `created_at`), plus a `source_entry` pointer back to that lane's history
  file it was promoted from.
- **Bootstrap, per lane.** The first `record` call *for a given lane*,
  when that lane's baseline file does not exist yet, promotes that run to
  the baseline automatically — this is a one-time initialization per lane,
  not a recurring auto-advance, and is exactly the "this run becomes the
  baseline, no comparison performed" state #338's acceptance criteria
  requires, applied independently to sentinel and to comprehensive (the
  comprehensive lane bootstraps its own baseline on its own first
  successful run, unaffected by whether sentinel has already bootstrapped
  or been promoted). Every `record` call after a lane's bootstrap leaves
  that lane's baseline file untouched.
- **Promotion, per lane.** `benchmark_history.py promote-baseline --lane
  <sentinel|comprehensive>` is the only other way a lane's baseline file
  changes — an explicit, maintainer-run command (by default promoting that
  lane's most recent history entry, or a `--entry` given explicitly),
  never invoked automatically by `record` or by any Routine step, and
  scoped to the `--lane` given (default `sentinel`, matching the pre-#431
  single-lane behavior).

### Why not last-known-good or a rolling baseline

The issue explicitly requires a documented rationale, not just "previous
successful run" (naive last-known-good), because that ratchets: a small
undetected degradation becomes tomorrow's accepted reference, and the
known-good signal erodes silently. Two of the three suggested
alternatives were considered and set aside for a concrete, structural
reason rather than by default:

- **Last-known-good** needs a "was this run clean" judgment to decide
  whether to advance — but classifying a run as clean-vs-regressed is
  exactly [#339](https://github.com/amirbena/code-review-skill/issues/339)'s
  drift-vs-noise responsibility, which does not exist yet and which this
  issue's own Non-goals forbid re-deriving. Wiring an automatic
  last-known-good advance today would mean either duplicating #339's
  future logic here or advancing on a weaker, ad-hoc signal (e.g.
  `overall_verified`, which only proves the run *executed*, not that its
  *findings* held steady) — reintroducing the exact ratcheting risk this
  policy exists to avoid.
- **A rolling baseline (median of last N runs)** dampens single-run noise,
  but noise-vs-signal is again #339's classification, not #338's; a
  median baseline would also stop being a single, cite-able artifact a
  human can read and would need its own regression-report-shaped
  synthesis this document does not (and should not) invent.

A **pinned, deliberately-refreshed baseline** needs none of that: it never
moves on its own, so there is nothing to ratchet, and once #339 exists it
can compare every nightly run against the same fixed reference until a
maintainer reviews the accumulated deltas and consciously promotes a new
one — precisely the model `regression-report.md` §8 already establishes
for baseline refreshes ("an explicit human action ... only when the
deltas are understood and accepted"). This document does not invent a new
baseline-refresh philosophy; it applies the existing one to the nightly
path.

## 5. Interfaces for #339

- `benchmark_history.py show-baseline --history-root <dir> --lane
  <sentinel|comprehensive>` prints that lane's current baseline artifact
  (or `{"baseline_exists": false, "lane": "..."}` before that lane's first
  run), in exactly the shape `regression-report.md`'s `compare()` expects
  as its baseline input. `--lane` defaults to `sentinel`, matching the
  pre-#431 single-lane call shape.
- Each lane's `history[-<lane>]/<date>-<sha>.json` file is a complete,
  self-contained candidate run for that lane: #339 reads that lane's
  newest entry and diffs it against that same lane's baseline file using
  the existing regression-report contract, unchanged. #339's own
  `runtime_platform/benchmark/scripts/benchmark_drift.py` CLI takes already-extracted
  baseline/candidate metrics files directly (`detect`/`sync --baseline-
  file`/`--candidate-file`) rather than a history root, so no #339 code
  change was required by #431 — only that whoever prepares those input
  files for a given lane's Routine run reads that lane's own baseline
  (`--lane sentinel` or `--lane comprehensive`), never the other lane's.
  Verified: `benchmark_drift.py` performs no `corpus_id` check itself, so
  the fail-closed cross-lane guard for a genuinely raw baseline-vs-
  candidate pairing still lives one layer down, in `compare()` (§3.2
  above) — this is unchanged by #431 and was true before it.
- Nothing here computes `has_regressions`, dedupes findings across
  runs, or opens/updates/closes a GitHub issue — that is entirely
  #339's job, reusing #55/#56/#57 unchanged (architecture model §6),
  applied once per lane with that lane's own tracking issue(s).

## Status and canonical home

This document is the authoritative contract for nightly full-corpus
history and baseline policy. `runtime_platform/benchmark/scripts/benchmark_history.py`
implements it; `tests/unit/benchmark/test_benchmark_history.py` proves the
bootstrap, retention, and promotion behavior above. A conflict discovered
later is resolved by updating this document through a reviewed change,
not by silently deviating in code.
