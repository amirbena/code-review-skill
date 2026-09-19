# Canonical Result Record and Persistence

Part of the [scheduled benchmark operations decision record](decision-record.md)
(GitHub Issue [#464](https://github.com/amirbena/code-review-skill/issues/464)).
Research / design only; not packaged into either Skill archive.

It fixes the durable representation of one scheduled benchmark run, chooses
where it lives, and shows why the alternatives lost.

## 1. The logical record: sealed result plus receipt

One run has one logical record made of two immutable parts written by two
different parties:

- the **sealed result** — written once by the execution side, before any
  GitHub write; hashed; never edited;
- the **receipt** — written once by the publisher after publication;
  holds only what did not exist at seal time (record commit, comment and
  issue links). The receipt is a *summary*, never authoritative for
  idempotency — markers on the GitHub objects are
  ([`drift-issue-lifecycle-and-recovery.md`](drift-issue-lifecycle-and-recovery.md) §6).

**Run identity.** `run_id = <lane>-<YYYYMMDDTHHMMSSZ>-<repo_sha[:12]>`, using
the run's UTC start time. It replaces the `<date>-<sha[:12]>` key of
[`benchmark_history.py`](../scripts/benchmark_history.py), which cannot
represent two runs of one lane on one SHA and day (evidence E6). `run_id`
is the publication idempotency key.

### Field table

Every field named in the issue's Scope is here. "Writer" is who produces it.

| Field group | Fields | Writer | Source |
| --- | --- | --- | --- |
| Identity | `schema` (`benchmark-result/v1`), `run_id`, `trigger` (`scheduled` \| `manual` \| `api`) | executor | new |
| Timestamps | `started_at`, `finished_at`, `sealed_at` (UTC ISO-8601) | executor | new; today only `timestamp` exists |
| Lane / mode | `lane` (`sentinel` \| `comprehensive`), `mode` (as invoked; `full` canonicalized to `sentinel`) | executor | [`benchmark_corpus_membership.py`](../scripts/benchmark_corpus_membership.py) `canonical_lane` |
| Corpus identity | `corpus.corpus_id` (whole-corpus digest), `corpus.case_count`, `corpus.membership_digest` | executor | [`benchmark_history.py`](../scripts/benchmark_history.py) digests, computed **at the evaluated SHA** |
| Repo / runtime / model version | `provenance.repo`, `provenance.repo_sha`, `provenance.ref`, `provenance.entrypoint_version`, `provenance.spec_sha256` (the prompt-spec and manifest hash); `runtime.runtime_name`, `runtime.runtime_version`, `runtime.model_id`, `runtime.adapter_id` | executor | [`runtime-execution-contract.md`](../runtime-execution-contract.md) §5 |
| Aggregate metrics | `aggregate.metrics`, `aggregate.severity`, `aggregate.duplicate_noise` — the aggregate objects the #55, #56, #57 contracts already define, stored verbatim | executor | [`missed-and-incorrect-findings.md`](../missed-and-incorrect-findings.md), [`severity-accuracy.md`](../severity-accuracy.md), [`duplicate-noise.md`](../duplicate-noise.md) |
| Per-case results | `cases[]`: `id`, `status`, `fixture_digest`, `metrics` (the #55 `CaseMetrics` fields), `severity` (the #56 `CaseSeverityAccuracy` fields), `duplicate_noise` (#57 per-case), `duration_s` | executor | the projections `benchmark_drift.py` already consumes |
| Verification | `verification.overall_verified`, `verification.runs[]` | executor | [`benchmark_routine_verify.py`](../scripts/benchmark_routine_verify.py) |
| Baseline reference | `baseline.state` (`bootstrap` \| `compared` \| `incomparable`), `baseline.run_id`, `baseline.record_sha256`, `baseline.comparable_case_ids`, `baseline.incomparable_cases[]` | executor | read from `baselines/<lane>.json` |
| Drift outcome | `drift.evaluated_scope` (case ids), `drift.observations[]`, `drift.confirmation` (parameters used), `drift.confirmed[]`, `drift.unconfirmed[]`, `drift.outcome` (`none` \| `drift` \| `not-evaluated` + reason), `drift.attribution` (`runtime-changed` when `model_id` or `runtime_version` differs from the baseline's) | executor | [`benchmark_drift.py`](../scripts/benchmark_drift.py) `classify_drift`, unchanged; records use its `DriftRecord` shape including `fingerprint` |
| Execution metadata | `execution.duration_s`, `execution.confirmation_reruns`, `execution.session_ref` (provider URL — informational, not durable), `execution.warnings[]` | executor | new |
| Reproduction provenance | `reproduction.command`, `reproduction.case_ids`, `reproduction.python_version`, `reproduction.nondeterminism` (states that model output is nondeterministic) | executor | new |
| Drift evidence | `drift.evidence[case_id]` — bounded raw excerpt (≤ 32 KiB per case) for **confirmed** drift only | executor | new |
| Raw output | `raw.bundle_sha256`, `raw.location` (handoff path); the bundle is **not** in git | executor | new |
| Publication (receipt) | `record_commit`, `record_permalink`, `evidence_comment_url`, `issue_links[]` (`fingerprint`, `issue`, `action`), `published_at`, `publisher_identity`, `publisher_run_url`, `steps_done[]` | publisher | new |

`content_sha256` is the SHA-256 of the canonical-JSON sealed body (sorted keys,
minimal separators, the same canonicalization
[`drift-detection-and-regression-lifecycle.md`](../drift-detection-and-regression-lifecycle.md)
§3 uses for fingerprints).

Two properties matter beyond the list:

- **The sealed record can feed `classify_drift` directly.** `cases[].metrics`
  and `cases[].severity` are exactly the per-case inputs
  [`benchmark_drift.py`](../scripts/benchmark_drift.py) loads, which is what
  makes drift evaluation derivable from a stored record rather than from
  hand-prepared files (evidence E11).
- **`cases[].fixture_digest`** is a per-fixture content digest. It is what
  allows a fixture edit to make one case *incomparable* instead of blocking
  the whole comparison (evidence E14; amendment A7).

## 2. Options compared

Criteria are the ones the issue names, plus the two this design adds:
immutability/linkability, and fit with the execution/publication boundary.

| Criterion | Git branch, everything | Actions artifacts | Issue comments | External store | **Bounded combination (chosen)** |
| --- | --- | --- | --- | --- | --- |
| Retention | permanent | 90 days by default; tied to workflow runs | permanent, editable/deletable | configurable | records permanent; raw time-bounded |
| Repository growth | **unbounded** — git keeps pruned history (E7); raw output makes it worst | none | none | none | bounded by compaction; measured trigger (§4) |
| Machine readability | high | medium (download, unzip) | low — prose plus JSON fences, pagination | high | high |
| Human inspection | high | low | highest | low | high (git file plus a human summary comment) |
| Baseline comparison | direct file read at a commit | needs run lookup and download | paginated scrape | direct | direct file read at a commit |
| Immutable exact link | commit permalink | run URL, expires | comment URL, editable | store URL | commit permalink |
| Needs a workflow to write | no | **yes** | no | no | no |
| App permissions | `Contents: write` | n/a | `Issues: write` | none on GitHub | `Contents: write` + `Issues: write` |
| New infrastructure | none | none | none | store, credential, cost | none |
| Boundary fit | publisher writes | written from a workflow run, not an App path | publisher writes | publisher writes | publisher writes |

**Why each rejected option lost**

- **Git, everything (raw per run):** a raw per-case review is tens of KiB;
  one comprehensive run is estimated at 1–5 MB, so 50–270 MB a year of
  *unrecoverable* history (git retains it even after a prune). Compaction
  is what keeps git viable, not pruning.
- **Actions artifacts:** default retention is 90 days, so a pinned baseline
  would expire; artifacts are tied to workflow runs and are not addressable by
  commit, so an issue could not link to immutable evidence. (The publication
  workflow exists, but it publishes to git, not to artifacts.)
- **Issue comments as the store:** comments are editable by their author,
  capped by the API (community-reported 65,536 characters), unschematized,
  and reading the last baseline means paging a thread. They remain valuable
  as the **human-facing index** — that is their role here.
- **External store as primary:** strongest on size and retention, but adds
  infrastructure, a credential, and cost; the maintainer selected a GitHub
  evidence surface. It stays the **escape hatch** if the growth trigger
  trips, and the M1 alternative for the handoff.

## 3. Layout on `benchmark-history`

```text
records/<lane>/<yyyy>/<run_id>.json      sealed result (immutable, create-only)
receipts/<lane>/<yyyy>/<run_id>.json     publisher receipt (immutable once written)
baselines/<lane>.json                    pointer, not a copy:
                                         { lane, run_id, record_path, record_sha256,
                                           corpus_id, source: "bootstrap"|"maintainer",
                                           promoted_at, promoted_by }
```

This lives only on an orphan history branch: never `main`, never Skill source.
[`nightly-history-and-baseline.md`](../nightly-history-and-baseline.md)'s
baseline policy is unchanged — pinned per lane, refreshed only by explicit
maintainer action, bootstrapped once per lane by the first published record.
Only the *representation* changes (a pointer plus the immutable record it
names, instead of a copied `baseline.json`).

**Evidence comment** on the lane's tracking issue, one per published run:
begins with `<!-- benchmark-run:<run_id> -->`, then a short human summary
(lane, SHA, model, executed/total, drift outcome, baseline state) and two
**immutable commit-pinned permalinks** — the record and the baseline — plus
links to any issues acted on. It is an index and a notification, not the
store.

## 4. Retention, growth, and the trigger

- **Records and receipts are never pruned.** The "newest 90" rule of
  [`nightly-history-and-baseline.md`](../nightly-history-and-baseline.md)
  §3.3 does not bound git size (E7); it is replaced by compaction.
- **Raw bundles stay out of git.** They live in the handoff (the
  `claude/benchmark-result-<run_id>` ref, or the store prefix) until the
  receipt exists, and the staging ref is deleted 30 days after the receipt
  (`DELETE_STAGING_REF`). A bundle whose receipt does not exist is never
  deleted. Confirmed-drift evidence is copied into the record, bounded.
- **Growth estimate (assumptions, to be measured by the first real runs, not
  a claim):** compact per-case projection ≈ 0.5–1 KB → comprehensive record
  ≈ 50–110 KB for ~106 cases, sentinel ≈ 2–4 KB. Runs per year: comprehensive
  52; sentinel at most about 130 (under standard cron semantics a day-of-month
  step of 3 fires 10–11 times a month). Uncompressed ≈ 6 MB a year; git compresses JSON, so about
  1–2 MB a year — orders of magnitude inside GitHub's ideal
  repository size (< 1 GB) and far from the 50 MiB / 100 MiB file thresholds.
- **Trigger:** when the packed size of `benchmark-history` exceeds **100 MB**,
  or any single file exceeds **10 MB**, a maintainer decides between rotating
  to a new orphan branch and moving records to an external store. F2's first
  measurement is in [`../benchmark-result-schema.md`](../benchmark-result-schema.md) §5.

## 5. Baseline comparison against this store

The executor reads, read-only, `baselines/<lane>.json` and the record it
points to (fetched read-only from the `benchmark-history` ref through the
same repository access the checkout uses), verifies `record_sha256`, and compares only cases
whose `fixture_digest` matches (§1). A lane-membership or
lane-identity mismatch stays a total fail-closed refusal, exactly as
[`regression-report.md`](../regression-report.md) §3 demands; a
fixture-content divergence on individual cases downgrades only those cases
to `incomparable` and lists them (amendment A7, decision M4). No baseline
policy changes.
