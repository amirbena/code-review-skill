# Drift Detection and Regression Issue Lifecycle

Repository-development contract for GitHub Issue
[#339](https://github.com/amirbena/code-review-skill/issues/339), the
"Drift detection / regression issue lifecycle" layer of
[`../benchmark-measurement-architecture/benchmark-measurement-architecture-model.md`](../benchmark-measurement-architecture/benchmark-measurement-architecture-model.md)
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

Exactly two comparable persisted runs, in the shapes
[`nightly-history-and-baseline.md`](nightly-history-and-baseline.md) §3–§5
already produce:

- `baseline` — `benchmark_history.py show-baseline`'s artifact (a
  `regression-report.md` §2 `BaselineArtifact`: `results`, `corpus_id`,
  `adapter_id`).
- `candidate` — the newest `history/<date>-<sha>.json` entry's `results`.

Both are joined by case `id` exactly as
[`regression-report.md`](regression-report.md) §3–§4 already defines —
this document never rejoins or re-parses them. For each case present in
both runs, it consumes three **already-existing, unmodified** projections
of that pair:

| Projection | Source | What this document reads from it |
| --- | --- | --- |
| Missed/incorrect-finding metrics | `tests/reference/benchmark/benchmark_metrics.py::compute_case_metrics` (#55) | `missed_keys` — the `key` of every `required` expected-findings entry with no `MATCH` in that run. |
| Severity accuracy | `tests/reference/benchmark/benchmark_severity.py::compute_case_severity_accuracy` (#56) | `exact_rate` — the case's exact-match rate over its matched set (`None` when nothing matched). |
| Regression report | `tests/reference/benchmark/benchmark_report.py::compare` (#53) | `has_regressions`, per-case classification — informational context carried into the issue body, never re-derived. |

`tests/reference/benchmark/*` are the **only executable projections**
of #53/#54/#55/#56/#57 that exist in this repository today (each
contract's "Status and canonical home" section says so explicitly — none
of the five has an installed runtime component yet). Consuming them from
`scripts/benchmark/benchmark_drift.py`, a production script, is therefore
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
| `severity-accuracy-drop` | Both `baseline.exact_rate` and `candidate.exact_rate` (#56) are defined (matched set non-empty in both runs) **and** `baseline.exact_rate - candidate.exact_rate > SEVERITY_EXACT_RATE_TOLERANCE` (`1/5`, i.e. more than a 20-percentage-point drop, `scripts/benchmark/benchmark_drift.py::DEFAULT_SEVERITY_EXACT_RATE_TOLERANCE`). | A fixed tolerance absorbs single-run flakiness in a small matched set; only a drop exceeding it is meaningful. |

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
  use the closed sentinel `"-"` (`scripts/benchmark/benchmark_drift.py::CASE_LEVEL_FINDING_KEY`)
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

### 4.2 Finding candidate issues cheaply, without free-text search

Every issue this document opens or updates carries the label
`benchmark-regression` (`scripts/benchmark/benchmark_drift.py::REGRESSION_LABEL`).
A sync pass lists **open** issues with that label (`gh issue list --label
benchmark-regression --state open --json number,body,labels`), extracts
each one's marker (§4.1), and builds a `fingerprint → issue` map. The
label narrows the candidate set to a small, cheap listing; the marker,
not the label or any text in the listing, is what decides a match.

`gh issue list --limit N` caps *total* results, not results per page, so a
fixed limit would silently truncate this listing once more than `N`
labeled issues are open — breaking §4.3's one-issue-per-fingerprint
guarantee without any error. `list_labeled_issues`
(`scripts/benchmark/benchmark_drift.py::GhCliIssueClient.list_labeled_issues`)
retries with a doubling `--limit` until a response is smaller than
requested — proof nothing was left out — up to a fixed safety ceiling
(`MAX_ISSUE_LIST_LIMIT`) past which it raises rather than looping forever
against a pathological response.

### 4.3 Transitions

For the drift records classified from the current comparison (§2) and the
map from §4.2:

| Situation | Action |
| --- | --- |
| A fingerprint with **no** matching open issue | **Open** one issue: title is human-readable (`Benchmark drift: <case_id> — <drift_type>`, informational only, never matched against); body starts with the §4.1 marker, then a short description, then the §5 machine-readable metadata block; labeled `benchmark-regression`. |
| A fingerprint that **matches** an already-open issue | **Append a dated comment** to that issue with the current run's metadata (§5) and an updated "still reproducing" note. Never open a second issue for the same fingerprint. |
| A previously open, fingerprinted issue whose fingerprint is **absent** from the current drift set | The regression no longer reproduces: **append a resolution comment** and **close** the issue — unless §4.4's override applies. |
| A drift record that is noise (§2) | No action of any kind — it never reaches this table because it is never classified into a drift record in the first place. |

Exactly one issue exists per fingerprint at any time: §4.2's map is keyed
by fingerprint, so a fingerprint already open is always routed to the
comment branch, never the create branch.

### 4.4 Maintainer override: `keep-open`

Before auto-closing a resolved fingerprint (§4.3, row 3), the sync pass
checks whether the issue currently carries the label `keep-open`
(`scripts/benchmark/benchmark_drift.py::KEEP_OPEN_LABEL`). If it does, the
issue is **left open** and **not commented on for resolution** — a human
relabeled it to say "investigate further before closing," and that
decision is authoritative until they remove the label themselves. This is
the only escape hatch from auto-closure; it is never bypassed by any
other signal (recurrence count, elapsed time, or drift severity).

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

`baseline`/`candidate` `date`/`repo_sha` are read straight from the #338
history entries (`nightly-history-and-baseline.md` §3.2) — this document
never computes or guesses either value.

## 6. The GitHub-mutation boundary is thin and injectable

`scripts/benchmark/benchmark_drift.py` defines a small `GitHubIssueClient`
protocol (`list_labeled_issues`, `create_issue`, `comment`, `close`) and
one real implementation, `GhCliIssueClient`, that shells out to `gh` —
the same pattern `scripts/benchmark/run_benchmark_routine.py::_post_evidence`
already established for this repository's benchmark tooling (temp-file
bodies via `--body-file`, `gh issue create`/`comment`, return codes
surfaced as errors). No new GitHub-mutation library or pattern is
introduced. `sync_regressions` (the lifecycle orchestrator, §4) takes a
`GitHubIssueClient` as a parameter and never imports or constructs
`GhCliIssueClient` itself, so every test in
[`../../tests/unit/benchmark/test_benchmark_drift.py`](../../tests/unit/benchmark/test_benchmark_drift.py)
runs against an in-memory fake client and makes zero network calls.

## 7. Status and canonical home

This document is the authoritative contract for drift detection and the
regression-issue lifecycle. `scripts/benchmark/benchmark_drift.py`
implements it; `tests/unit/benchmark/test_benchmark_drift.py` proves the
fingerprinting stability/distinctness and the four lifecycle transitions
against a fixed baseline+candidate pair (open, dedupe-comment, keep-open
override, close-on-resolution) plus the noise-never-triggers-an-issue
guarantee. A conflict discovered later is resolved by updating this
document through a reviewed change, not by silently deviating in code.
