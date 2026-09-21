# Publication CLI: `sweep` and `watchdog`

Repository-development contract for GitHub Issues
[#471](https://github.com/amirbena/code-review-skill/issues/471) (`sweep`, F5) and
[#472](https://github.com/amirbena/code-review-skill/issues/472) (`watchdog`, F6) of Epic
[#466](https://github.com/amirbena/code-review-skill/issues/466); design record
[#464](https://github.com/amirbena/code-review-skill/issues/464). Like the rest of
[`./`](README.md) it is **not packaged into either Skill archive**.

It owns what the deterministic publisher **does**: the commands, their credentials,
the handoff file `sweep` reads, the order and gates of one publication, how issues
are reconciled, how a failed pass is retried, and (§7) what `watchdog` watches. The design it implements is
[`scheduled-operations/execution-publication-boundary.md`](scheduled-operations/execution-publication-boundary.md)
§2 and §5,
[`scheduled-operations/drift-issue-lifecycle-and-recovery.md`](scheduled-operations/drift-issue-lifecycle-and-recovery.md)
§1–§4 and §6, and
[`scheduled-operations/canonical-result-and-persistence.md`](scheduled-operations/canonical-result-and-persistence.md)
§3; this document restates none of their rationale. The record and receipt shapes
are [`benchmark-result-schema.md`](benchmark-result-schema.md); the manifest is
[`schedule-spec.md`](schedule-spec.md).

| Artifact | Owns |
| --- | --- |
| [`scripts/publish_benchmark.py`](scripts/publish_benchmark.py) | The entrypoint (`sweep`, `watchdog`). |
| [`publisher/`](publisher/) | The pass itself: `sweep.py` (order, gates, persist, receipt), `validation.py` (the §2 gates), `lifecycle.py` (drift issues), `render.py` and `markers.py` (post bodies and idempotency markers), `github_api.py` (the REST ports), `memory.py` (in-memory ports for tests and `--dry-run`). |
| [`publisher/watchdog.py`, `publisher/health.py`](publisher/) | `watchdog`: the gap rule and missed-run issues, and the health-status comment. |

It never runs the benchmark, calls a model, or derives drift: it reads
`drift.confirmed[]` and fingerprints from the sealed record (`watchdog` reads record metadata only). Nothing under
`publisher/` imports the benchmark entrypoint, the reviewer adapter, or
`benchmark_drift.py`, and none shells out; a test enforces it
([`test_benchmark_publisher_boundary.py`](../../tests/unit/benchmark/test_benchmark_publisher_boundary.py)).
`benchmark_drift.py` keeps classification and fingerprints only: its in-Routine
`GhCliIssueClient`, `sync_regressions`, and `sync` subcommand are retired.

## 1. Invocation

```bash
python3 runtime_platform/benchmark/scripts/publish_benchmark.py sweep [--once] [--dry-run] \
    [--run-id RUN_ID [--accept-unattributed]] [--manifest PATH] [--app-slug SLUG] [--run-url URL]
```

- **Credentials.** Three App installation tokens, from `BENCHMARK_CONTENTS_TOKEN`
  (`contents: write`), `BENCHMARK_ISSUES_TOKEN` (`issues: write`), and optionally
  `BENCHMARK_READ_TOKEN` (`contents: read`, else the contents token). A token that
  is not an installation token (`ghs_…`) is refused. No other variable is read —
  never `GH_TOKEN`, `GITHUB_TOKEN`, or a `gh` login — so there is **no
  personal-identity fallback path**; a missing token stops the run before any call.
- **Identity.** The acting identity is `<app-slug>[bot]` (`--app-slug` or
  `BENCHMARK_APP_SLUG`). It is printed to stderr before anything acts, and every
  comment and issue the publisher creates is checked against it: an author that
  is not that identity stops the sweep.
- **`--once`** is a local or disaster-recovery pass. Without it the command must
  run under GitHub Actions (`GITHUB_ACTIONS`, `GITHUB_RUN_ID`), whose run URL
  goes in each receipt; a local pass records `local-once` in `steps_done` and
  the repository URL as `publisher_run_url`. Local `--once` alongside a workflow
  run is the operator's responsibility.
- **`--dry-run`** reads GitHub and plans in full — record, receipt, and issue
  actions in the printed report — but every write lands in memory.
- **`--run-id`** publishes only that run (pattern-validated). With
  **`--accept-unattributed`** it also accepts a ref whose server-side attribution
  is *unavailable*; attribution that contradicts the allowlist is never accepted.
- **Output.** A JSON report on stdout, refusals and failures on stderr. Exit `0`
  when every ref is published or already published, `1` on any refusal, failure,
  or abort, `2` for a usage or credential error.

## 2. The handoff file

A sealed result is the file **`benchmark-result.json`** at the root of the tip of
`claude/benchmark-result-<run_id>`: the canonical `benchmark-result/v1` JSON of
[`benchmark-result-schema.md`](benchmark-result-schema.md). The execution side
(F4, [#470](https://github.com/amirbena/code-review-skill/issues/470)) writes it;
the publisher reads it at the ref's tip SHA and treats it as data.

## 3. One publication, in order

Refs are processed in ascending `sealed_at` (parsed, so fractional seconds order correctly); a refusal never blocks the next.
A malformed ref — unreadable or offset-less `sealed_at`, unparsable or absurdly nested JSON, or an unexpected error while processing it — is refused or reported `failed` for that ref alone and never stops the sweep. Start-up is fail closed: a manifest that is not provisioned, or a missing label of
the four, aborts the whole sweep before any write.

| Step | Does | On failure |
| --- | --- | --- |
| validate | The boundary §2 gates, in order — `schema` (known version, shape), `content-hash`, `verification`, `provenance` (lane in the manifest, ref name encodes `run_id`) plus semantic conformance, `origin`, `conflict`, and `baseline` (a compared record's baseline is in this lane's history and matches its recorded hash; a baseline from the other lane is refused). | **Refuse and report** with the gate name; nothing is written or repaired. |
| persist | One create-only commit of `records/<lane>/<yyyy>/<run_id>.json`, plus `baselines/<lane>.json` (`source: bootstrap`) when the record is the lane's first and none exists. | A same-hash existing record is a no-op success; a different hash is a refused `conflict`. |
| reconcile | Drift issues, §4. | The run stays unpublished; the next sweep resumes. |
| announce | One evidence comment on the lane's tracking issue, beginning `<!-- benchmark-run:<run_id> -->`, with commit-pinned permalinks and the issues acted on. | As above. |
| receipt | `receipts/<lane>/<yyyy>/<run_id>.json` (`benchmark-receipt/v1`). | As above. |

Reconcile runs before announce so the evidence comment can link the issues it
acted on and an issue never links a record that does not exist; the receipt is a
summary and never authoritative for idempotency. **A run is published when its
receipt exists.** A receipted run is never re-gated: it is checked only against its stored record and receipt hashes, so a later manifest or validator change cannot strand it. A run with a record and no receipt resumes at reconcile; origin
attestation is not repeated for a record already persisted.

**Origin.** The repository activity API must show a `branch_creation` of that exact
ref, at the fetched SHA, by an actor in `publication.pusher_allowlist`. Commit
author metadata is never used. No activity for the ref at all is *unavailable*:
refused, unless the maintainer dispatches that `run_id` with
`--accept-unattributed` (recorded as `origin-accepted-by-dispatch`).

## 4. Drift issues

- **Recognition.** A drift issue is one labelled `benchmark-regression`, whose
  first line carries `<!-- benchmark-regression:<fingerprint> -->`, **and** whose
  author is the publisher identity. Marker recognition counts only comments the
  publisher identity authored (A14): a foreign marker neither suppresses a post nor
  is edited, and a foreign-authored issue carrying a marker is ignored.
- **Issue-worthy** only for `drift.confirmed[]` of a `compared` record. Bootstrap
  and incomparable records touch no issue.
- **Open** once per fingerprint (`max_new_issues_per_run`, then the rest are
  listed as deferred and re-considered next run); **comment** on a recurrence
  while open, guarded by `<!-- benchmark-applied:<run_id>:<fingerprint> -->`
  (also in a newly created body, so a retry does not comment on its own issue);
  after a create, re-list the fingerprint and keep the lowest-numbered issue,
  closing the other with a pointer.
- **Recurrence after closure** opens a new issue with `Recurrence of #N`, found in
  a scan of the 200 most recent closed drift issues; a closed issue is never
  reopened.
- **Resolution is lane-aware (A9).** An open issue closes only when, for **every**
  scheduled lane whose latest published record covers its case (evaluated **and**
  comparable), that record's `drift.confirmed[]` lacks the fingerprint; if no lane
  covers it, it is left as is, and `keep-open` (read fresh) blocks the close. The
  case comes from the issue's own metadata block; metadata that is unreadable, or whose
  fingerprint is not the issue's own, leaves the issue alone. "Latest" is by run start time among receipted runs; if another
  lane's latest record cannot be loaded, nothing is closed.
- A record older than its lane's newest published record is **superseded**: it is
  published but drives no issue.
- Free text from a record is neutralized (`<!--` cannot survive into a post), and
  `runtime-changed` attribution is stated on every issue and comment.

## 5. Failure handling

Failure-table cases in
[`drift-issue-lifecycle-and-recovery.md`](scheduled-operations/drift-issue-lifecycle-and-recovery.md)
§6, and the tests that exercise them
([`test_benchmark_publisher_sweep.py`](../../tests/unit/benchmark/test_benchmark_publisher_sweep.py)):

| Case | Behavior |
| --- | --- |
| 3 publication fails | The run stays unpublished; the next sweep re-reads the handoff. No benchmark re-run. |
| 4 evidence post fails | Record exists; the next sweep posts the comment once (marker). |
| 5 issue created, later step fails | The retry finds the open fingerprint and its applied marker; no duplicate comment. A failed close retries without a second resolution comment. |
| 7 duplicate or retried run | Distinct `run_id`s share one issue and each gets its own marked comment. |
| 8 App unavailable | HTTP `401`/`403` stops the sweep (`FatalPublicationError`), never falls back; `5xx` and network errors fail only that run. |
| 9 overlapping passes | Duplicate open issues collapse to the lowest number. |
| 10 same `run_id`, different hash | Refused `conflict`; nothing is overwritten. |
| 11 no baseline, or all incomparable | No issue opened, commented on, or closed. |
| 12 foreign marker | Ignored (§4). |

A retried pass reports only the issue actions it takes; an issue it already closed
cannot be re-listed, so a resumed run's receipt may omit that `closed` link.

## 6. Staging refs

A staging ref is deleted (`DELETE_STAGING_REF`) only when its receipt exists, its
content hash matches the receipt, and the receipt is at least 30 days old. An
unpublished ref is never deleted.

## 7. `watchdog`

```bash
python3 runtime_platform/benchmark/scripts/publish_benchmark.py watchdog [--once] [--dry-run] \
    [--sweep-report PATH] [--manifest PATH] [--app-slug SLUG]
```

It makes a run that never happened visible ([failure-table case 6](scheduled-operations/drift-issue-lifecycle-and-recovery.md));
it cannot make the run happen, retries nothing, and never executes the benchmark or judges drift. Credentials, acting
identity, `--once`, and `--dry-run` are §1's, with one narrowing: it never writes `benchmark-history`, so when
`BENCHMARK_READ_TOKEN` is set the history client carries that read token alone and `BENCHMARK_CONTENTS_TOKEN` is not needed.
Start-up is fail closed exactly as for `sweep`: an unprovisioned manifest or a missing label aborts before any write, and so
does any failure to read history, so an unreadable lane never opens an issue. Exit `0` unless the pass aborted; an overdue
lane is the watchdog working, not failing.

**The gap rule.** For each scheduled lane the reference is the latest **published** record (its receipt exists) that is
intact (`content_sha256` matches), `verification.overall_verified`, and `trigger: scheduled`. The lane is overdue when
`now − finished_at > max_gap_hours` from the manifest (strictly greater). Only elapsed time is computed: no weekday, local
time, timezone, or slot appears in this code (a test scans it), so nothing here owns a zone or DST (#431). A manual or `api`
run never counts. A lane with **no** such record has no reference instant, so nothing is opened for it and the health status
says so; the first scheduled run is a provisioning check, not something gap arithmetic can watch.

**Missed-run issues.** Labelled `benchmark-missed-run`; first line `<!-- benchmark-missed-run:<lane> -->`; recognized only
when authored by the publisher identity (A14).

| Lane state | Action |
| --- | --- |
| overdue, no open issue | Open one, naming the last verified run, its `finished_at`, the gap, and the checklist to run. |
| overdue, issue open | Comment at most once per `watchdog.missed_run_comment_interval_hours`, measured from the last `<!-- benchmark-missed-run-notice:<lane>:<UTC> -->` stamp the publisher itself wrote. |
| not overdue, issue open | Comment `<!-- benchmark-missed-run-resolved:<lane>:<run_id> -->` (once) and close. |
| more than one open issue for a lane | Keep the lowest number; comment a pointer on, and close, the rest (also after every create). |

A missed-run issue is not held open by `keep-open`; it closes exactly when the lane recovers.

**Health status.** One comment on `health_issue`, first line `<!-- benchmark-health-status -->`, found, created and
edited only as a comment the publisher identity authored; a foreign comment carrying the marker is data and is never
edited (case 12). It holds facts only, no "as of" time, and is edited only when its rendered body differs. `--sweep-report`
takes the JSON `sweep` printed: an `ok` report with no `aborted` reason marks "last successful publication sweep" as this
pass's time; anything else keeps the value the previous comment carried, and none yet reads `not reported`. Run it right
after `sweep` for that to mean what it says. Pending handoffs are `claude/benchmark-result-*` refs without a receipt; their age
is the oldest readable `sealed_at`, in whole hours. Sample (asserted against the renderer by
[`test_benchmark_publisher_watchdog.py`](../../tests/unit/benchmark/test_benchmark_publisher_watchdog.py)):

<!-- sample-health-status -->
````markdown
<!-- benchmark-health-status -->

**Scheduled benchmark health**

| Lane | State | Latest verified scheduled run | Finished (UTC) | Model | Drift outcome | Max gap | Missed-run issue |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `sentinel` | on schedule | `sentinel-20260916T010000Z-5a5a5a5a5a5a` | 2026-09-16T01:01:00Z | `claude-sonnet-5` | not evaluated (bootstrap: first record for this lane is the baseline) | 96 h | — |
| `comprehensive` | on schedule | `comprehensive-20260914T010000Z-5b5b5b5b5b5b` | 2026-09-14T01:01:00Z | `claude-sonnet-5` | not evaluated (bootstrap: first record for this lane is the baseline) | 192 h | — |

- Open drift issues: 0
- Open missed-run issues: 0
- Sealed but unpublished handoffs: none
- Last successful publication sweep: 2026-09-19T01:01:00Z

Edited in place by the publisher identity, and only when a fact above changes.
````
