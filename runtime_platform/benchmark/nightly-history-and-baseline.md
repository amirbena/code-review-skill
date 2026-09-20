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

> **Amended by [#467](https://github.com/amirbena/code-review-skill/issues/467)**
> (Epic [#466](https://github.com/amirbena/code-review-skill/issues/466); design
> record [#464](https://github.com/amirbena/code-review-skill/issues/464),
> [`scheduled-operations/`](scheduled-operations/README.md), amendments A1–A13
> in [`contract-reconciliation.md`](scheduled-operations/contract-reconciliation.md)).
> Sections changed by an amendment carry its ID, e.g. **(A4)**; everything not
> marked is unchanged, including the baseline *policy* (§4). This document
> states the amended contract. `benchmark_history.py` and
> `benchmark_regression_lifecycle.py` still implement the pre-amendment
> behavior until the implementation issues of Epic #466 land, and those issues
> cite this text; `run_benchmark_routine.py` was brought to it by [#470](https://github.com/amirbena/code-review-skill/issues/470).

## 1. Scope

- The scheduling policy and full-corpus invocation choice for a Claude
  Cloud Routine run (§2).
- Persisted, comparable history keyed by run identity (lane, UTC start, and
  commit SHA — A4), plus the runtime/model/Skill metadata needed to interpret
  a result later (§3).
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
- The Cloud Routine's own checkout/SHA-pinning/completion-verification
  mechanics — [#415](https://github.com/amirbena/code-review-skill/issues/415)/
  [`cloud-routine-integration.md`](../../docs/benchmark/cloud-routine-integration.md) own all
  of it, unchanged. Its evidence persistence and credential bounding are
  amended (A1, A2) in that document (§4, §7).
- Re-deriving match/metrics logic already owned by
  [#54](https://github.com/amirbena/code-review-skill/issues/54)/[#55](https://github.com/amirbena/code-review-skill/issues/55)/[#56](https://github.com/amirbena/code-review-skill/issues/56)/[#57](https://github.com/amirbena/code-review-skill/issues/57).
- Any PR-blocking behavior, or any GitHub Actions workflow that schedules,
  runs, re-runs, or evaluates the benchmark — superseded by
  [#391](https://github.com/amirbena/code-review-skill/issues/391), not
  reopened here. A publication-only workflow that only publishes an
  already-sealed result is a different thing and is permitted (A13, §2).

## 2. Scheduling policy

**Two-tier scheduling (#431).** A maintainer configures **two** Claude Cloud
Routines (`cloud-routine-integration.md` §9.1), not one:

| Lane | `--mode` | Maximum gap between verified scheduled runs | Corpus |
| --- | --- | --- | --- |
| Sentinel | `sentinel` (deprecated alias: `full`) | ≤ 96 h | the 4 permanent canonical cases (`--corpus-dir`'s own top-level, non-recursive glob) |
| Comprehensive | `comprehensive` | ≤ 8 d (192 h) | every `benchmark-case/v2` fixture in the corpus tree, discovered programmatically |

Each lane also supports the same Routine's manual/on-demand trigger for an
off-schedule run; a manual run (`trigger: manual`) never satisfies a lane's
maximum gap.

**Cadence is a maximum gap, not an exact interval (A11).**

- "Every 3 days" is not an exact cron interval: the minimum interval is one
  hour, and under standard cron semantics a day-of-month step of 3 restarts
  each month, giving gaps of 1–3 days. The contract is therefore the
  **maximum gap** above; the intended cadence is recorded as text, with
  `max_gap_hours` (sentinel 96, comprehensive 192), in the repository-owned
  schedule spec ([`schedule-spec.md`](schedule-spec.md)).
- "Friday night" at a 01:00 start is ambiguous (early Friday versus early
  Saturday). The comprehensive schedule names the **Israel-local weekday on
  which its 01:00 start falls**; that weekday (Friday) is fixed in the schedule
  spec and the Routine configuration, never described as a bare "Friday night".
- The **04:00 maximum-completion window is a target, not a promise**: it is
  unmeasured against ~106 sequential invocations plus confirmation re-runs,
  and is to be measured before it is relied on.
- DST behavior is not stated in the Routines documentation beyond
  local-zone entry with automatic conversion — it is verified, not assumed.
- Comprehensive membership is **derived, never a hard-coded count**: it was
  106 `benchmark-case/v2` fixtures on 2026-09-19 (informational; #431's text
  said "~89").

Both lanes target a **01:00 Israel-local start**; each run can begin a few
minutes late. Timezone/DST handling is a **Cloud Routine
scheduling-configuration responsibility, never repository runtime logic** —
the schedule itself is set in Israel local time (or UTC with the correct
seasonal offset) in the Routine's own product surface;
`runtime_platform/benchmark/scripts/` computes no timezone, which is why the
missed-run rule is gap-based (the watchdog is specified in
[`scheduled-operations/drift-issue-lifecycle-and-recovery.md`](scheduled-operations/drift-issue-lifecycle-and-recovery.md)
§5). `cloud-routine-integration.md` §7 assigns sizing
run frequency against Claude subscription usage and Routine run limits to the
maintainer, and the comprehensive lane is far more expensive per run than
sentinel's 4 cases — which is why its gap is longer.

**Collision is expected and independently baselined, not deduplicated.** The
two schedules periodically coincide; when they do, both Routine runs execute,
verify, and are published independently, each with its own `run_id` and
against its own lane baseline (§3–§4). Deduplicating a same-night collision is
out of scope.

**Order of a run (A2, A8, A12).** Evaluation happens on the execution side,
before anything is written to GitHub:

```text
Routine (thin prompt spec)
  → fresh checkout; run the entrypoint for a named lane with the model id;
    exit non-zero on failure
Entrypoint (repository code at the pinned SHA)
  → run the lane's cases → positively verify completion
  → read the lane baseline (read-only)
  → evaluate drift, with in-run confirmation
  → SEAL the canonical result to the handoff           ← commit point
Publication (deterministic; publication-only; benchmark-publication App)
  → validate → persist the record → announce run evidence
  → reconcile drift issues → receipt
```

The pre-amendment order was persist → evaluate → issues, with evaluation a
separate step over hand-prepared files. A run is **verified only once sealed**;
before the seal nothing is persisted, so an unverified or unsealed run persists
nothing (the unchanged fail-closed rule). After the seal the result is durable
independent of the Routine session, and a run that sealed but failed to publish
is republished from the seal — **never by re-running the benchmark**. The
execution side holds no provisioned GitHub write credential; repository-owned
execution code performs no GitHub mutation other than the seal, itself a
bounded, provider-mediated write. The seal, handoff transport, and publication
steps are specified in
[`scheduled-operations/execution-publication-boundary.md`](scheduled-operations/execution-publication-boundary.md).

**Thin Routine prompt spec (A12).** The multi-step prompt of the pre-amendment
template — dependency installs, `gh` evidence posting, and a history-branch
push — is replaced by a spec that says only: fresh checkout, run the
entrypoint for the named lane with the model id, exit non-zero on failure.
All logic is repository code at the pinned SHA, so provider-side prompt drift
cannot change behavior. The literal template is
`cloud-routine-integration.md` §9.

`run_benchmark_routine.py --results-out PATH` (added by #338, additive and
backward compatible) remains a local output flag: it writes the concatenated
raw per-invocation `run_benchmark.py` output only when the run passed positive
completion verification, mirroring the vehicle's fail-closed rule. It is no
longer the hand-off to persistence — the seal is. For `--mode comprehensive`
the output is the concatenation of one `run_benchmark.py` invocation per
discovered fixture (`cloud-routine-integration.md` §2.1).

**Never blocks PR or `main`; never a contributor prerequisite (A13).** No
GitHub Actions workflow schedules, runs, re-runs, or evaluates the benchmark,
and none is a contributor or merge prerequisite — there is no independent
Actions benchmark execution path from the retired #255 workflow
([#420](https://github.com/amirbena/code-review-skill/issues/420)), and
`.github/workflows/**` does not invoke anything above. A **publication-only**
workflow (`schedule` sweep and watchdog, manual `workflow_dispatch`) that reads
sealed records, touches no model, and judges nothing is permitted and is a
different thing; see `runtime-execution-contract.md` §2.2. No contributor
needs benchmark credentials, a Routine, or `benchmark-history` branch push
access for a normal PR or merge.

## 3. Persisted history

### 3.1 Storage location (A1, A2)

The authoritative store is a compact, schema-versioned, content-hashed record
per run on a dedicated **`benchmark-history`** branch — an isolated orphan
branch: not `main`, not any reviewed branch, not packaged Skill resources, not
an existing `docs/` analytics surface, and distinct from #182's execution
telemetry (#131's workflow-observation export does not exist — #131 is closed
`not planned` as a product-layer capability; §6 of the cross-component
architecture model). A branch, not a release artifact, was chosen because it
is inspectable with ordinary `git`/GitHub tooling, needs no separate
retention configuration, and keeps evidence inside the same repository #339
already has issue access to. Evidence-issue comments are the **human index and
notification** for each published run, never the store
([`cloud-routine-integration.md`](../../docs/benchmark/cloud-routine-integration.md)
§4). Raw per-case output is not stored in git (§3.3).

The branch is written by the `benchmark-publication` GitHub App, through the
deterministic publication step that runs after a run is sealed — **never by the
Routine** (A2; the pre-amendment "Routine pushes the history branch under the
maintainer identity" step is withdrawn). Records are persisted create-only and
hash-checked: an existing record with the same content hash is success, one
with a different hash is a conflict that is refused, never overwritten.

Layout (replaces the per-lane `history/` and `history-comprehensive/`
directories and the `baseline*.json` copies):

```text
records/<lane>/<yyyy>/<run_id>.json     sealed result (immutable, create-only)
receipts/<lane>/<yyyy>/<run_id>.json    publisher receipt (immutable once written)
baselines/<lane>.json                   per-lane baseline pointer (§4)
```

### 3.2 Run identity, record shape, and comparability (A4, A7)

One run has one logical record made of two immutable parts written by
different parties: the **sealed result** (`benchmark-result/v1`, written once
by the execution side before any GitHub write, hashed, never edited) and the
**receipt** (written once by the publisher; holds only what did not exist at
seal time — record commit, comment and issue links — and is a summary, never
authoritative for idempotency).

**Run identity (A4).** `run_id = <lane>-<YYYYMMDDTHHMMSSZ>-<repo_sha[:12]>`,
using the run's UTC start time. It replaces the `<date>-<repo_sha[:12]>` key,
which cannot represent two runs of one lane on one SHA and UTC day (the second
was refused as an overwrite). `run_id` is the publication idempotency key, and
the constant evidence marker is replaced by per-run markers on GitHub objects
(`<!-- benchmark-run:<run_id> -->` on the evidence comment; drift-issue
markers in
[`drift-detection-and-regression-lifecycle.md`](drift-detection-and-regression-lifecycle.md)
§4.1). `content_sha256` is the SHA-256 of the canonical-JSON sealed body
(sorted keys, minimal separators — the canonicalization #339 §3 uses for
fingerprints).

The sealed result carries these field groups (the exact schema is
[`benchmark-result-schema.md`](benchmark-result-schema.md); the enumerated field
table is in
[`scheduled-operations/canonical-result-and-persistence.md`](scheduled-operations/canonical-result-and-persistence.md)
§1):

- **identity and timing** — `schema`, `run_id`, `trigger` (`scheduled` |
  `manual` | `api`), `lane`, `mode`, `started_at`, `finished_at`,
  `sealed_at`;
- **corpus identity** — `corpus_id`, case count, membership digest, computed
  at the evaluated SHA;
- **provenance and runtime metadata** — repository SHA and ref, runtime
  name/version, model id, adapter id (the set
  [`runtime-execution-contract.md`](runtime-execution-contract.md) §5
  requires);
- **aggregates** — the #55/#56/#57 aggregate objects, stored verbatim;
- **per-case results** — `cases[]`: `id`, `status`, `fixture_digest`, and the
  #55/#56/#57 per-case projections, stored verbatim and never recomputed by
  the storage layer;
- **verification** — `overall_verified` and the per-invocation results;
- **baseline reference** — state (`bootstrap` | `compared` | `incomparable`),
  the baseline `run_id` and `record_sha256`, comparable and incomparable case
  ids;
- **drift outcome** — evaluated scope, confirmed and unconfirmed drift,
  outcome, and attribution (`runtime-changed` when the model id or runtime
  version differs from the baseline's);
- **bounded evidence** — a raw excerpt (≤ 32 KiB per case) for **confirmed**
  drift only, and the raw bundle's hash; the bundle itself is not in git.

**Lane identity (#431).** `lane` (`"sentinel"` or `"comprehensive"`) lets each
scheduled lane maintain and compare against its own baseline: it is derived
from `mode`, canonicalized so the deprecated `full` alias always records
`"sentinel"` (`benchmark_corpus_membership.canonical_lane`). `corpus_id` keeps
its pre-#431 meaning and is lane-specific: the sentinel lane digests every
top-level `*.yaml` id + content (non-recursive); the comprehensive lane
digests the recursively discovered `benchmark-case/v2` membership
(`benchmark_history.py::comprehensive_corpus_digest`). Comprehensive
membership is a strict superset of sentinel's, so the two `corpus_id` values
are never equal for the same corpus tree. `corpus_id` mirrors
`regression-report.md` §2's definition and is computed the way the reference
implementation (`runtime_platform/benchmark/reference/benchmark_report.py::corpus_digest`)
computes it.

**Comparability (A7).** `corpus_id` remains the whole-corpus identity, and a
**lane-identity mismatch stays a total fail-closed refusal**, exactly as
`regression-report.md` §3 demands: a record is only ever compared against a
baseline of the same lane, so a sentinel record is never compared against a
comprehensive baseline. Cases added to or removed from a lane's corpus since
the baseline are not a lane-identity mismatch; they are reported as added and
removed cases (`regression-report.md` §3) and never refuse the comparison.
What is amended is fixture-content divergence *within one lane*. The
comprehensive `corpus_id` digests every fixture, so any corpus change alters
it — the corpus tree changed in 41 commits in the 31 days to 2026-09-19 — and
a total block plus manual re-promotion would leave comparison refused almost
continuously. Each case therefore carries a `fixture_digest`; a fixture edit
downgrades **only that case** to `incomparable`, listed in the record, and the
remaining cases are still compared. Incomparable cases never open, comment on, or close an
issue. No baseline-policy change: #431's "no new guard code" holds for lane
identity, and per-case `fixture_digest` handling is the one addition.

**Nothing is recomputed, and only verified runs are sealed.** The record
stores the runner's own per-case shape; this document never reinterprets a
result (§4.3 of the architecture model's runtime contract: "actual Skill
semantics, not a second reviewer implementation" applies equally to storage).
Sealing re-validates that every case's `status` is `executed` and
`overall_verified` is true before anything is persisted, and the publisher
re-checks and refuses otherwise — a corrupted or partial run must never become
a persisted record or the bootstrap baseline (§4), mirroring
`regression-report.md` §2's `BaselineArtifact.from_run` guard.

### 3.3 Retention and growth (A5)

**Records and receipts are never pruned.** The pre-amendment "newest 90 entries
per lane" rule is withdrawn as a size bound: pruning removed files from the
working tree only, and git history keeps every pruned entry, so it never
bounded repository size. Growth is bounded by compaction (compact per-case
projections; raw output stays out of git) and by a measured trigger: when the
packed size of `benchmark-history` exceeds **100 MB**, or any single file
exceeds **10 MB**, a maintainer decides between rotating to a new orphan
branch and moving records to an external store. The first real records
measure actual record size before this is relied on.

Raw bundles are time-bounded in the handoff, not in git: the staging ref that
carries a sealed result is deleted 30 days after its receipt exists, and a
bundle whose receipt does not exist is never deleted. Confirmed-drift evidence
is copied into the record, bounded as in §3.2.

## 4. Baseline policy

**Chosen policy: a pinned reference baseline per lane, refreshed only by
an explicit maintainer action — never automatically on every scheduled
run.** Sentinel and comprehensive each maintain their own baseline
artifact, independently; nothing here lets one lane's baseline stand in
for the other's.

- `baselines/<lane>.json` (A6) holds, per lane, a **pointer, not a copy**:
  `{ lane, run_id, record_path, record_sha256, corpus_id, source:
  "bootstrap" | "maintainer", promoted_at, promoted_by }`, naming the
  immutable record on `benchmark-history` that is the baseline. The
  baseline's content is that record, in `regression-report.md` §2's shape
  (`results`, `corpus_id`, `adapter_id`). This replaces the pre-amendment
  `baseline.json` / `baseline-comprehensive.json` copies.
- **Bootstrap, per lane.** The first published record *for a given lane*,
  when that lane's baseline pointer does not exist yet, becomes the baseline
  — a one-time initialization per lane, not a recurring auto-advance, and
  exactly the "this run becomes the baseline, no comparison performed" state
  #338's acceptance criteria require, applied independently to sentinel and
  to comprehensive. The publisher performs only this bootstrap (A6); every
  later publication leaves the pointer untouched.
- **Promotion, per lane.** A maintainer promotes explicitly, with their own
  credentials, by writing the lane's pointer under a ruleset bypass scoped to
  the `benchmark-history` branch only. Promotion is never
  performed by the publisher, a Routine step, or `record`, and never
  automatically; by default the target is that lane's most recent record, or
  an explicit `run_id`. The local `benchmark_history.py promote-baseline
  --lane` command, which edits `baseline*.json`, is the pre-amendment
  mechanism and is replaced under Epic #466.

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

## 5. Interfaces for #339 (A8)

- **Baseline read.** The executor reads, read-only, `baselines/<lane>.json`
  and the record it points to (fetched from the `benchmark-history` ref
  through the same repository access the checkout uses), verifies
  `record_sha256`, and compares only cases whose `fixture_digest` matches
  (§3.2). The pre-amendment `benchmark_history.py show-baseline --lane`
  command, which printed a baseline artifact in the shape `regression-report.md`'s
  `compare()` expects, is superseded by this read.
- **Drift is derived from the record, not from hand-prepared files.** The
  sealed result's `cases[]` (per-case metrics and severity) are exactly the
  per-case inputs `runtime_platform/benchmark/scripts/benchmark_drift.py`'s
  `classify_drift` consumes, so drift is evaluated during the run — with
  in-run confirmation, [`drift-detection-and-regression-lifecycle.md`](drift-detection-and-regression-lifecycle.md)
  §2.1 — and its outcome is sealed into the record. Each lane is evaluated
  against its own baseline only, once per lane. The pre-amendment
  `detect`/`sync --baseline-file`/`--candidate-file` inputs, which a caller
  had to prepare, are no longer the path.
- Nothing in the history or baseline layer computes `has_regressions`,
  dedupes findings across runs, or opens, updates, or closes a GitHub
  issue. Issue lifecycle is #339's, executed by the publisher from the
  sealed result, reusing #55/#56/#57 unchanged (architecture model §6),
  applied once per lane.

## Status and canonical home

This document is the authoritative contract for scheduled benchmark history
and baseline policy, **as amended by #467 (A1–A13)**.
`runtime_platform/benchmark/scripts/benchmark_history.py` implements the
pre-amendment shape and is brought to this text by the implementation issues
of Epic [#466](https://github.com/amirbena/code-review-skill/issues/466);
`tests/unit/benchmark/test_benchmark_history.py` proves the pre-amendment
bootstrap, retention, and promotion behavior until then. A conflict
discovered later is resolved by updating this document through a reviewed
change, not by silently deviating in code.
