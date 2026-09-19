# Drift Detection and Regression Issue Lifecycle

Repository-development contract for GitHub Issue
[#339](https://github.com/amirbena/code-review-skill/issues/339), the
"Drift detection / regression issue lifecycle" layer of
[`../../docs/benchmark-measurement-architecture/benchmark-measurement-architecture-model.md`](../../docs/benchmark-measurement-architecture/benchmark-measurement-architecture-model.md)
§3, consuming [#338](https://github.com/amirbena/code-review-skill/issues/338)'s
persisted, comparable nightly history
([`nightly-history-and-baseline.md`](nightly-history-and-baseline.md)) as
its input. Parent: [#332](https://github.com/amirbena/code-review-skill/issues/332).

Like the rest of [`./`](README.md), this is a **repository-development
doc: not packaged into either Skill archive**, and no packaged Skill
resource depends on it.

This document owns exactly one thing: turning a baseline-vs-candidate
comparison into **at most one deduplicated, lifecycle-managed GitHub
issue per meaningful regression** — never nightly noise, never a raw JSON
dump. It reuses [`regression-report.md`](regression-report.md) (#53) and
the [#54](https://github.com/amirbena/code-review-skill/issues/54)/[#55](https://github.com/amirbena/code-review-skill/issues/55)/[#56](https://github.com/amirbena/code-review-skill/issues/56)/[#57](https://github.com/amirbena/code-review-skill/issues/57)
metrics **unchanged** — it does not redefine matching, counting, or
severity-accuracy logic.

> **Amended by [#467](https://github.com/amirbena/code-review-skill/issues/467)**
> (Epic [#466](https://github.com/amirbena/code-review-skill/issues/466); design
> record [#464](https://github.com/amirbena/code-review-skill/issues/464),
> [`scheduled-operations/`](scheduled-operations/README.md), amendments A1–A13
> in [`contract-reconciliation.md`](scheduled-operations/contract-reconciliation.md)).
> Amended sections carry their IDs — **A4** per-run markers, **A8** evaluation
> order, in-run confirmation and the publisher boundary, **A9** lane-scoped
> resolution, **A10** label prerequisites and recurrence. Drift types,
> tolerance, fingerprint, hidden-marker identity, `keep-open`, and the
> machine-readable metadata are unchanged. `benchmark_drift.py` still
> implements the pre-amendment behavior until the implementation issues of
> Epic #466 land, and those issues cite this text.

## Non-goals

- Benchmark execution, scheduling, or history persistence — owned
  entirely by #338.
- Any PR-blocking behavior.
- A hosted dashboard or alerting integration (Slack/PagerDuty/etc.) — a
  GitHub issue is the deliverable.
- Re-deriving match/metrics logic already owned by #54/#55/#56/#57 — this
  document only adds a drift-vs-noise policy and fingerprinting **on top**
  of their existing output shapes.

## 1. Inputs

Exactly two comparable runs of **one lane** (A8), evaluated **during the run
on the execution side** — not as a separate Routine "sync step" over
hand-prepared files — from the shapes
[`nightly-history-and-baseline.md`](nightly-history-and-baseline.md) §3–§5
define:

- `baseline` — the record the lane's baseline pointer names (a
  `regression-report.md` §2 `BaselineArtifact`: `results`, `corpus_id`,
  `adapter_id`), read read-only.
- `candidate` — the current run's own per-case results, the `cases[]` of the
  canonical result being produced, restricted to the cases that are
  comparable (matching `fixture_digest`, `nightly-history-and-baseline.md`
  §3.2). Because `cases[]` carries exactly the per-case metrics and severity
  `classify_drift` consumes, drift derives from the record itself. A
  `bootstrap` baseline, or a case listed `incomparable`, produces no drift
  record.

Both are joined by case `id` exactly as
[`regression-report.md`](regression-report.md) §3–§4 already defines —
this document never rejoins or re-parses them. For each case present in
both runs, it consumes three **already-existing, unmodified** projections
of that pair:

| Projection | Source | What this document reads from it |
| --- | --- | --- |
| Missed/incorrect-finding metrics | `runtime_platform/benchmark/reference/benchmark_metrics.py::compute_case_metrics` (#55) | `missed_keys` — the `key` of every `required` expected-findings entry with no `MATCH` in that run. |
| Severity accuracy | `runtime_platform/benchmark/reference/benchmark_severity.py::compute_case_severity_accuracy` (#56) | `exact_rate` — the case's exact-match rate over its matched set (`None` when nothing matched). |
| Regression report | `runtime_platform/benchmark/reference/benchmark_report.py::compare` (#53) | `has_regressions`, per-case classification — informational context carried into the issue body, never re-derived. |

`runtime_platform/benchmark/reference/*` are the **only executable projections**
of #53/#54/#55/#56/#57 that exist in this repository today (each
contract's "Status and canonical home" section says so explicitly — none
of the five has an installed runtime component yet). Consuming them from
`runtime_platform/benchmark/scripts/benchmark_drift.py`, a production script, is therefore
a deliberate exception, not a precedent for scripts generally depending
on `tests/`: the alternative — re-deriving match/metrics logic inline —
is exactly what this issue's Non-goals and #338's Non-goals both forbid.
When #53–#57 eventually install a canonical non-test-only component (per
each contract's "Status and canonical home"), `benchmark_drift.py`'s
imports move there unchanged; this paragraph is the one place that
migration touches.

## 2. Meaningful drift vs. noise

A **drift record** is emitted only for one of three closed, explicitly
enumerated conditions. Anything else — including every example the issue
calls out as noise — never produces a drift record, and therefore never
reaches the issue lifecycle (§4).

| `drift_type` | Condition (candidate vs. baseline, same case `id`) | Rationale |
| --- | --- | --- |
| `missed-required-finding` | A `key` in `candidate.missed_keys` (#55) that was **not** in `baseline.missed_keys` — a required expected finding the baseline satisfied that the candidate no longer does. | The single most direct "the reviewer got worse" signal: a previously-matched required finding stopped being reported. |
| `decision-flip` | `baseline.missed_keys` is empty (every required finding was satisfied) **and** `candidate.missed_keys` is non-empty (at least one now is not). | The case-level "matches its expected decision/required findings" state flipped from true to false — the exact wording of the issue's first example. |
| `severity-accuracy-drop` | Both `baseline.exact_rate` and `candidate.exact_rate` (#56) are defined (matched set non-empty in both runs) **and** `baseline.exact_rate - candidate.exact_rate > SEVERITY_EXACT_RATE_TOLERANCE` (`1/5`, i.e. more than a 20-percentage-point drop, `runtime_platform/benchmark/scripts/benchmark_drift.py::DEFAULT_SEVERITY_EXACT_RATE_TOLERANCE`). | A fixed tolerance absorbs single-run flakiness in a small matched set; only a drop exceeding it is meaningful. |

**Noise — never produces a drift record, by construction:**

- An optional finding appearing or disappearing — `missed_keys` (#55) only
  ever contains `required` entries; optional-entry churn is invisible to
  this policy by construction, not by a separate exclusion rule.
- A change in `false_positives` / `incorrect_indices` / `near_misses` /
  `tolerated_unexpected` (#55) — not read by §2 at all.
- A `severity-accuracy-drop` at or below the fixed tolerance.
- An `exact_rate` of `None` in either run (nothing matched — not a
  comparable rate; see `severity-accuracy.md` §4's `null` rule).
- A case present in only one of the two runs (`added_case_ids` /
  `removed_case_ids`, `regression-report.md` §3) — reported by the
  regression report itself, out of this policy's fingerprintable scope.
- A `regression-report.md` `improvement` or an opposite-direction flip
  (`decision-flip`'s condition is one-directional; the reverse direction
  is handled by the lifecycle's auto-resolution in §4, not as a new
  drift record).

### 2.1 Confirmed drift (A8)

[`runtime-execution-contract.md`](runtime-execution-contract.md) §2.2 requires
the pipeline to evaluate *confirmed* drift, and a model-backed reviewer is
nondeterministic, so a single observation is not issue-worthy. **Confirmation
is performed on the execution side, inside the run, before sealing.** For each
classified drift, only that case is re-run through the existing `selected`
mode up to a configured number of additional times; every observation is
re-classified with the same unchanged `classify_drift`; a fingerprint is
**confirmed** when it appears in at least a configured threshold of the
observations. The number of drifting cases confirmed per run is bounded — more
than the bound marks the run systemic and stops confirming — and drift left
unconfirmed when the run's time budget ends is recorded as such and
re-evaluated next run. The parameters (re-runs, threshold, per-run cap) live in
the repository-owned schedule spec; the protocol and the values recommended
for it are in
[`scheduled-operations/drift-issue-lifecycle-and-recovery.md`](scheduled-operations/drift-issue-lifecycle-and-recovery.md)
§2.

A drift seen but not confirmed is recorded as unconfirmed, counted as a flake
signal, and **never published as an issue**. Confirmation adds a
pre-publication gate to §2–§4; it does not change the drift types, the
fingerprint, or the tolerance.

## 3. Stable regression fingerprinting

```text
fingerprint = sha256(canonical_json({
    "case_id": <case id>,
    "drift_type": <one of the three §2 values>,
    "expected_finding_key": <expected-findings entry `key`, or "-" for a
                              case-level drift_type>,
}))
```

- **`case_id`** and **`expected_finding_key`** are not invented here: a
  case's `id` is the runner-contract/fixture-format identity already used
  to join runs (§1), and `expected_finding_key` is the fixture's own
  `expected.findings` entry `key` (`fixture-format.md` §8.1/§8.4) — the
  same `key` #55's `missed_keys` already carries verbatim. `decision-flip`
  and `severity-accuracy-drop` are case-level, not finding-level, so they
  use the closed sentinel `"-"` (`runtime_platform/benchmark/scripts/benchmark_drift.py::CASE_LEVEL_FINDING_KEY`)
  rather than inventing a new per-finding identity for them.
- **Canonical JSON** — `json.dumps(..., sort_keys=True, separators=(",", ":"))`
  over exactly those three fields, so the fingerprint is a pure function
  of the triple: the caller's own key ordering or whitespace, and any
  extra context fields a caller might carry alongside the triple, never
  affect it.
- The fingerprint carries **no run-specific data** (no date, no SHA, no
  rate value) — two nights that independently detect the *same*
  regression must produce the *same* fingerprint, which is what makes
  deduplication (§4) possible without free-text matching.

## 4. GitHub issue lifecycle

### 4.1 The hidden marker — the only match key

Every issue this document opens embeds its fingerprint as the **first
line of the issue body**, as an HTML comment:

```text
<!-- benchmark-regression:<64-hex-char fingerprint> -->
```

Matching an incoming drift record against an existing issue is done
**only** by extracting this marker from a candidate issue's body with a
fixed regular expression and comparing fingerprints — **never** by
matching on the issue title, free-text body content, or GitHub's own
full-text search ranking. A human is free to edit the visible title/body
prose (e.g. to add commentary) without breaking dedup, as long as the
marker line survives.

**Per-run marker (A4).** Issue identity is the fingerprint marker above,
unchanged. Every comment the publisher posts additionally carries a second
hidden marker, `<!-- benchmark-applied:<run_id>:<fingerprint> -->`, and before
commenting the publisher scans the issue's comments for it. That is what makes
a retried publication a no-op: one run applies to one issue at most once, and
a retry that finds its marker does nothing.

### 4.2 Finding candidate issues cheaply, without free-text search

Every issue this document opens or updates carries the label
`benchmark-regression` (`runtime_platform/benchmark/scripts/benchmark_drift.py::REGRESSION_LABEL`).
A sync pass lists **open** issues with that label (`gh issue list --label
benchmark-regression --state open --json number,body,labels`), extracts
each one's marker (§4.1), and builds a `fingerprint → issue` map. The
label narrows the candidate set to a small, cheap listing; the marker,
not the label or any text in the listing, is what decides a match.

`gh issue list --limit N` caps *total* results, not results per page, so a
fixed limit would silently truncate this listing once more than `N`
labeled issues are open — breaking §4.3's one-issue-per-fingerprint
guarantee without any error. `list_labeled_issues`
(`runtime_platform/benchmark/scripts/benchmark_drift.py::GhCliIssueClient.list_labeled_issues`)
retries with a doubling `--limit` until a response is smaller than
requested — proof nothing was left out — up to a fixed safety ceiling
(`MAX_ISSUE_LIST_LIMIT`) past which it raises rather than looping forever
against a pathological response.

**Labels are a provisioning prerequisite (A10).** `benchmark-regression`,
`keep-open`, `benchmark-missed-run`, and the tracking-issue label do not
exist until a maintainer creates them at provisioning. The publisher has no
label-creation capability and **fails closed at start-up** if a required
label is missing; a drift issue is never opened without its label.

### 4.3 Transitions

For the **confirmed** drift records (§2.1) classified from the current
comparison, and the map from §4.2:

| Situation | Action |
| --- | --- |
| A fingerprint with **no** matching open issue | **Open** one issue: title is human-readable (`Benchmark drift: <case_id> — <drift_type>`, informational only, never matched against); body starts with the §4.1 marker, then a short description, then the §5 machine-readable metadata block; labeled `benchmark-regression`. If a *closed* issue carries the same fingerprint, the new issue links it (`Recurrence of #N`) — see §4.3.2. |
| A fingerprint that **matches** an already-open issue | **Append a dated comment** to that issue with the current run's metadata (§5) and an updated "still reproducing" note, guarded by the per-run marker (§4.1). Never open a second issue for the same fingerprint. |
| A previously open, fingerprinted issue whose fingerprint is **absent** from `drift.confirmed[]` of **every scheduled lane that currently covers its case** (§4.3.1) | The regression no longer reproduces: **append a resolution comment** and **close** the issue — unless §4.4's override applies. |
| Drift that is noise (§2), unconfirmed (§2.1), or seen against a `bootstrap` baseline or an `incomparable` case | No action of any kind — it never reaches this table, and it neither opens, comments on, nor closes anything. |

Exactly one issue is open per fingerprint at any time: §4.2's map is keyed by
fingerprint, so a fingerprint already open is always routed to the comment
branch, never the create branch.

#### 4.3.1 Resolution is scoped by lane coverage (A9)

An open issue for case *C* is closed only when, for **every scheduled lane
whose latest published record covers *C*** — *C* is in that record's evaluated
scope **and** comparable — that record's `drift.confirmed[]` does not contain
the fingerprint. If no lane currently covers *C*, the issue is left as is.
Consequences:

- A sentinel record can never close an issue for a comprehensive-only case.
- An issue for a canonical case (covered by both lanes) stays open until
  *both* lanes have stopped reproducing it — at most one comprehensive cycle
  later.
- A record that is unverified, unpublished, or not `compared` resolves
  nothing.

#### 4.3.2 Recurrence after closure (A10)

A recurrence while an issue is open is a comment (§4.3). A recurrence **after
closure** opens a **new** issue that links the previous one (`Recurrence of
#N`), found by a bounded listing of closed `benchmark-regression` issues and
a marker match. The publisher does **not** reopen a closed issue: it carries a
resolution comment and possibly a maintainer's triage, and the cost of a new
issue is one extra issue per genuine recurrence.

### 4.4 Maintainer override: `keep-open`

Before auto-closing a resolved fingerprint (§4.3, row 3), the sync pass
checks whether the issue currently carries the label `keep-open`
(`runtime_platform/benchmark/scripts/benchmark_drift.py::KEEP_OPEN_LABEL`). If it does, the
issue is **left open** and **not commented on for resolution** — a human
relabeled it to say "investigate further before closing," and that
decision is authoritative until they remove the label themselves. This is
the only escape hatch from auto-closure; it is never bypassed by any
other signal (recurrence count, elapsed time, or drift severity). Only users
with triage rights can apply the label, so it only ever *prevents* a close;
it cannot cause a mutation.

## 5. Machine-readable metadata

Every create/comment this document posts includes a fenced ` ```json `
block, so another system can consume the regression without prose
scraping:

```json
{
  "fingerprint": "<the sha256 hex from §3>",
  "case_id": "<case id>",
  "drift_type": "missed-required-finding | decision-flip | severity-accuracy-drop",
  "expected_finding_key": "<key, or \"-\">",
  "baseline": {"date": "<baseline history entry date>", "repo_sha": "<baseline repo_sha>"},
  "candidate": {"date": "<candidate history entry date>", "repo_sha": "<candidate repo_sha>"},
  "detected_at": "<UTC ISO-8601 of this sync pass>"
}
```

`baseline`/`candidate` `date`/`repo_sha` are read straight from the baseline
record and the sealed result (`nightly-history-and-baseline.md` §3.2) — this
document never computes or guesses either value.

**Extended by A4.** Every create and comment the publisher posts also carries
`lane`, `run_id`, a commit-pinned permalink to the sealed record, and a
commit-pinned permalink to the baseline record it was compared against, and —
when the sealed record's `drift.attribution` is `runtime-changed` (the model
or runtime version differs from the baseline's) — says so. The link names the
*exact* evidence, so a later record or a baseline promotion cannot change what
an issue points at. `runtime-changed` never suppresses an issue: hiding it
would hide a real regression.

## 6. The GitHub-mutation boundary is thin, injectable, and on the publication side (A8)

Drift **classification** stays on the execution side (§1–§3, §2.1) and its
outcome is sealed into the run's canonical result. The lifecycle in §4 is
executed by the **publisher** — the deterministic publication step that runs
after the seal — which consumes the sealed record's `drift.confirmed[]` and
fingerprints and **never recomputes them**. `sync_regressions` and the `gh`
client therefore move out of the Routine into the publisher, whose import graph
excludes the benchmark entrypoint, the reviewer adapter, and `classify_drift`
(enforced by a policy test,
[`scheduled-operations/publication-architecture.md`](scheduled-operations/publication-architecture.md)
§5). Classification, drift types, tolerance, and fingerprint are unchanged.

The mutation boundary itself stays small and injectable.
`runtime_platform/benchmark/scripts/benchmark_drift.py` defines a small
`GitHubIssueClient` protocol (`list_labeled_issues`, `create_issue`,
`comment`, `close`) and one real implementation, `GhCliIssueClient`, that shells
out to `gh` (temp-file bodies via `--body-file`, `gh issue create`/`comment`,
return codes surfaced as errors); under this amendment the real client
authenticates as the `benchmark-publication` App inside the publication job,
never as the maintainer's personal identity. `sync_regressions` (the lifecycle
orchestrator, §4) takes a `GitHubIssueClient` as a parameter and never imports
or constructs `GhCliIssueClient` itself, so every test in
[`../../tests/unit/benchmark/test_benchmark_drift.py`](../../tests/unit/benchmark/test_benchmark_drift.py)
runs against an in-memory fake client and makes zero network calls.
runs against an in-memory fake client and makes zero network calls.

## 7. Two-lane operation (#431) — lifecycle corrected (A9)

#431 split scheduled execution into a sentinel lane and a comprehensive lane
with independently keyed baselines (`nightly-history-and-baseline.md` §4).
Its acceptance criterion required verifying that this document produces
correct, non-cross-comparing signals for both lanes. That verification was
**incomplete and is corrected here**: the statement held for comparison and
classification, not for the issue lifecycle.

- **Comparison and classification never cross lanes.** `classify_drift`
  (§1–§2) is handed a `baseline`/`candidate` pair from one lane's own record
  and baseline, never the other lane's. `benchmark_drift.py` itself performs
  no `corpus_id` check — that guard lives in `compare()`
  (`benchmark_report.py`, `nightly-history-and-baseline.md` §3.2) one layer
  down. Each lane is evaluated once, separately, against its own baseline.
- **The lifecycle did not hold to that (A9).** Before this amendment, §4.3
  closed any open labeled issue whose fingerprint was absent from the current
  drift set, regardless of which lane produced that set. A sentinel
  evaluation with zero drift records would therefore close an open issue for a
  case only the comprehensive lane covers — the sentinel run says nothing about
  that case. Resolution is now **scoped by lane coverage** (§4.3.1); the
  "non-cross-comparing" statement is true of `compare()`, not of an unscoped
  lifecycle.
- **A shared fingerprint across lanes is intentional, not a defect.** §3's
  fingerprint is `{case_id, drift_type, expected_finding_key}` — it does
  not include a lane identifier. Because the comprehensive lane's
  membership is a strict superset of the sentinel lane's (it includes the
  same 4 canonical cases, `nightly-history-and-baseline.md` §3.2), the
  *same* `case_id` regressing under both lanes independently produces the
  *same* fingerprint by design: it is the same underlying case behaving
  the same way, observed by two schedules, and correctly dedupes to one
  GitHub issue rather than two duplicates. §5's metadata block distinguishes
  which run detected each recurrence, so no signal is lost by sharing the
  issue. Adding a lane discriminator to the fingerprint was considered and
  rejected: it would turn one genuine regression signal into two
  separately-tracked issues for the same case, working against §4.2's own
  cheap-dedup goal. Coverage-scoped resolution (§4.3.1) is what makes the
  shared fingerprint safe.
- **The tracking-issue thread and the regression-issue label are
  different concepts, both already per-run/per-fingerprint.** The Cloud
  Routine's evidence tracking issue is one thread per lane
  (`cloud-routine-integration.md` §4); the `benchmark-regression`-labeled
  issues this document opens (§4) are keyed by fingerprint, not by lane or
  by evidence-issue thread, for the reason above.

## 8. Status and canonical home

This document is the authoritative contract for drift detection and the
regression-issue lifecycle, **as amended by #467 (A4, A8, A9, A10)**.
`runtime_platform/benchmark/scripts/benchmark_drift.py` implements the
pre-amendment shape and is brought to this text by the implementation issues
of Epic [#466](https://github.com/amirbena/code-review-skill/issues/466);
`tests/unit/benchmark/test_benchmark_drift.py` proves the fingerprinting
stability/distinctness and the four pre-amendment lifecycle transitions
against a fixed baseline+candidate pair (open, dedupe-comment, keep-open
override, close-on-resolution) plus the noise-never-triggers-an-issue
guarantee. A conflict discovered later is resolved by updating this
document through a reviewed change, not by silently deviating in code.
