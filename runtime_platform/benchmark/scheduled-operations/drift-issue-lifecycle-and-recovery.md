# Drift → Issue Lifecycle, Failure and Recovery

Part of the [scheduled benchmark operations decision record](decision-record.md)
(GitHub Issue [#464](https://github.com/amirbena/code-review-skill/issues/464)).
Research / design only; not packaged into either Skill archive.

It fixes the deterministic boundary between "a benchmark observed a
difference" and "a GitHub issue exists", and what happens when any step of
the chain fails. Evaluation stays in the benchmark
([`drift-detection-and-regression-lifecycle.md`](../drift-detection-and-regression-lifecycle.md),
#339); the App only executes a publication plan derived from the sealed
result and never judges review output.

## 1. What is issue-worthy

An issue may be opened or commented on for a fingerprint **only if all** hold:

1. **Classified** by the unchanged #339 policy — one of the three closed drift
   types (`missed-required-finding`, `decision-flip`, `severity-accuracy-drop`)
   with the unchanged `{case_id, drift_type, expected_finding_key}` fingerprint.
   Noise (§2 of that document) never reaches this table.
2. **Comparable** — the record's `baseline.state` is `compared` and the case is
   in `baseline.comparable_case_ids`. `bootstrap` and `incomparable` cases never
   open, comment, or close anything; the evidence comment says why.
3. **Confirmed** — the fingerprint is in `drift.confirmed[]` (§2). A drift seen
   once and not confirmed is in `drift.unconfirmed[]`: it is recorded, counted
   as a flake signal, and never published as an issue.

`drift.attribution = runtime-changed` (model or CLI version differs from the
baseline's; [`runtime-execution-contract.md`](../runtime-execution-contract.md)
§5's purpose) does **not** suppress an issue — hiding it would hide a real
regression — but it is stated on the issue and the evidence comment so a
maintainer can tell a Skill change from a model change.

## 2. Confirmation (the "debounce")

[`runtime-execution-contract.md`](../runtime-execution-contract.md) §2.2 says
the pipeline must "evaluate confirmed drift" but nothing defines it (evidence
E12), and a model-backed reviewer is nondeterministic. Decision:
**confirmation is performed on the execution side, inside the run**, before
sealing.

Protocol (parameters live in the manifest; recommended values are M3):

- For each classified drift, re-run **only that case** up to `reruns` (2)
  more times through the existing `selected` mode, and re-classify each
  observation with the same unchanged `classify_drift`.
- **Confirmed** = the same fingerprint appears in at least `threshold` (2) of
  the `1 + reruns` observations.
- At most `max_cases` (10) drifting cases are confirmed per run. If more drift,
  the run is flagged `drift.systemic = true` and confirmation stops; no issue
  is opened for the unconfirmed remainder, and the evidence comment says so.
- A confirmation rerun that does not pass positive completion verification fails
  the whole run closed: nothing is sealed, and the next scheduled run
  re-evaluates. The closed `unconfirmed` reasons deliberately have no value for
  an unverified rerun, so an unverified observation is never read as "not
  reproduced".
- If the run's time budget is exhausted, remaining drifts are recorded as
  `unconfirmed-timeout` — no issue this run; the next run re-evaluates.

| Alternative | Outcome |
| --- | --- |
| No confirmation (today) | one flaky observation opens an issue; the next clean run closes it — churn |
| Cross-run debounce only (2 consecutive runs) | delays a real regression by 6 days (sentinel) or 14 days (comprehensive) |
| In-run confirmation (chosen) | immediate for real regressions; bounded extra cost on drifting cases only |

This adds a pre-publication gate to #339 §2–§4; it does not change drift types,
the fingerprint, or the tolerance (amendment A8).

## 3. Identity, dedup, and provenance

- **Issue identity** is the fingerprint, unchanged, carried in the first-line
  hidden marker `<!-- benchmark-regression:<sha256> -->` of #339 §4.1.
- **Per-run idempotency** is a second hidden marker on every comment the
  publisher posts: `<!-- benchmark-applied:<run_id>:<fingerprint> -->`. Before
  commenting, the publisher scans the issue's comments for it. This is what
  makes a retried plan a no-op.
- **Publisher-authored comments only (A14).** A marker counts, and the
  publisher's own status comment is found, only on a comment authored by the
  publisher identity `<app-slug>[bot]` — the acting identity every publication
  run reports. This governs every comment scan: `benchmark-run:<run_id>` on
  tracking issues, `benchmark-applied:<run_id>:<fingerprint>` on drift issues,
  and the health-status comment on the pinned health issue. A comment from any
  other account, the maintainer's included, is data: it is neither a marker nor
  a status comment, it cannot suppress a post, and the publisher never edits it.
  The rule replaces locking the tracking and health issues, because the App's
  installation token cannot comment on a locked issue (observed: `HTTP 403`,
  [`provisioning-runbook.md`](provisioning-runbook.md) §4). If the App's own
  post is refused, publication fails closed (§6, cases 3 and 8) and is never
  retried under another identity.
- **Provenance and an immutable link** — every create and comment carries the
  #339 §5 metadata block extended with `lane`, `run_id`, a commit-pinned
  permalink to the sealed record, and a commit-pinned permalink to the baseline
  record it was compared against. The link names the *exact* evidence, so a
  later record or baseline promotion cannot change what an issue points at.
- **Label prerequisites** — `benchmark-regression`, `keep-open`,
  `benchmark-missed-run`, and the tracking-issue label do not exist today
  (E2). They are created by a maintainer at provisioning (F7). The publisher
  has no label-creation capability and **fails closed at start-up** if a
  required label is missing.

## 4. Recurrence, resolution, `keep-open`, spam bounds

**Recurrence while open** → comment (#339 §4.3, unchanged).

**Recurrence after closure** → open a **new** issue that links the previous
one (`Recurrence of #N`), found by a bounded listing of closed
`benchmark-regression` issues and a marker match. It does not reopen: a closed
issue carries a resolution comment and possibly a maintainer's triage; the
cost is one extra issue per genuine recurrence.

**Resolution is scoped by coverage** (amendment A9; fixes E13). An open issue
for case *C* is closed only when, for **every scheduled lane whose latest
published record covers *C*** (in its `drift.evaluated_scope` **and**
comparable), that record's `drift.confirmed[]` does not contain the
fingerprint. If no lane currently covers *C*, the issue is left as is.
Consequences:

- A sentinel record can never close an issue for a comprehensive-only case.
- An issue for a canonical case (covered by both lanes) stays open until
  *both* lanes have stopped reproducing it — at most one comprehensive
  cycle later.
- A record that is unverified, unpublished, or not `compared` resolves
  nothing.

`keep-open` (label present) blocks any auto-close, unchanged from #339 §4.4.
Labels are applied only by users with triage rights, so the label only ever
*prevents* a close; it cannot cause a mutation.

**Spam bounds.** Per published run: at most `max_new_issues` (5) new drift
issues; further confirmed drifts are listed in the evidence comment and
re-considered on the next run. Per fingerprint: one open issue. Evidence
comments: one per run. Missed-run: one open issue per lane.

## 5. Missed-run watchdog and health status

A watchdog is **needed**: a disabled Routine, a lapsed GitHub connection (the
Routine turns off after 72 hours without one), the daily run cap, a paused
subscription, or a crashed session all produce *no run and no signal* (E4,
and the Routines page's own warning that a green status is not success).

- **Rule (gap-based, no timezone logic).** For each scheduled lane, if
  `now − latest verified scheduled record.finished_at > max_gap_hours` from
  the manifest (sentinel 96, comprehensive 192), open one
  `benchmark-missed-run` issue for that lane (marker
  `<!-- benchmark-missed-run:<lane> -->`), comment at most once a day while it
  persists, and close it when a new verified scheduled record for the lane is
  published. A gap rule avoids computing wall-clock slots, so no repository
  code owns a timezone or DST (a #431 requirement).
- **What may schedule it.** The `schedule` trigger of the publication-only
  workflow, in the same concurrency group as publication. It is deterministic,
  reads record metadata only, needs no model, and never executes the benchmark
  or judges drift, so it is not the benchmark scheduling the fixed requirement
  forbids to Actions (amendment A13). It must not be a Routine (an LLM session
  with a daily run cap and a GitHub write path). The options and caveats
  are in [`publication-architecture.md`](publication-architecture.md) §6.
- **Health status.** One comment on a pinned health issue, authored by the
  publisher identity (§3) and edited in place, showing per lane: latest
  verified run and time, model, drift outcome, open drift and missed-run
  issues, sealed-but-unpublished handoffs and their age, and the last
  successful publication sweep. It is edited only when content changes.
- **Limit.** The watchdog cannot watch itself. A disabled or dropped schedule
  shows as a stale "last publication sweep" and accumulating
  `claude/benchmark-result-*` refs, and no alert is raised — external alerting
  is a non-goal, so the maintainer health checks in §7 are part of the design.
  In a public repository GitHub disables scheduled workflows after 60 days
  without repository activity, so "publication workflow enabled" is on that
  checklist.

## 6. Failure table

Idempotency key, retry boundary, retrying party, and what a maintainer sees.
"Sealed" is the commit point of [`execution-publication-boundary.md`](execution-publication-boundary.md) §4.

| # | Case | Idempotency key | Retry boundary | Retrying party | What a maintainer sees | Why nothing is lost or double-published |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | Benchmark fails verification, or the session dies before the seal | none — no `run_id` was sealed | none automatic | maintainer (`Run now`), prompted by the watchdog | non-green or no Routine run; after `max_gap_hours` a missed-run issue | An unsealed run is by definition **not a verified run**; this is the existing fail-closed rule. The guarantee starts at the seal. |
| 2 | Benchmark succeeds; the seal (handoff write) fails | `run_id` | the seal step — bounded in-session retries with backoff | the run itself, then case 1 if exhausted | as case 1 | The run exits non-zero rather than reporting success; it never leaves a half-sealed record (the seal is a single ref or object write, verified by hash before exit). |
| 3 | Sealed; publication fails (GitHub outage, App unavailable, key revoked) | `run_id` | each publication step, independently | the next scheduled sweep (automatic), or a `workflow_dispatch`, or a maintainer `--once` | pending-handoff count and age on the health status; `claude/benchmark-result-*` refs accumulating; a failed run in the Actions tab; stale "last publication sweep" | The sealed result is durable in the handoff; publication re-reads it. **No benchmark re-run is needed.** |
| 4 | Record persisted; evidence post fails | `<!-- benchmark-run:<run_id> -->` marker | the announce step | next sweep | record exists, run comment missing until next sweep | Persist is create-only and hash-checked: an existing record with the same hash is success. The comment is skipped if its marker exists. |
| 5 | Issue created; a later step (evidence, receipt) fails | fingerprint marker + `benchmark-applied` marker | from the first step lacking its marker | next sweep | issue exists with the run's comment; receipt appears later | Issues are created **after** the record commit, so an issue never links to a missing record. A retry finds the open fingerprint and takes the comment branch, guarded by the run marker. |
| 6 | Missed run | none (no run existed) | none automatic | maintainer; optional later: a workflow-fired Routine API trigger, deferred to F13 (needs a dispatch token) | `benchmark-missed-run` issue; health status shows overdue | The watchdog makes the absence visible; it cannot make the run happen. |
| 7 | Duplicate or retried run | distinct `run_id`s | not retried — both are valid runs | none | two records, two evidence comments | `run_id` prevents double-publication of one run. Two runs may each confirm the same drift; issues dedupe by fingerprint and each observation gets its own run-marked comment. Manual runs (`trigger: manual`) never satisfy the watchdog. |
| 8 | App unavailable, key rotated or revoked | `run_id` | token mint (`401`/`403` vs `5xx` reported distinctly) | the next sweep, after the maintainer restores the App | as case 3, with the workflow log showing the mint failure | No fallback to the maintainer's personal `gh` identity, ever. A manual `--once` run prints its acting identity and only proceeds under the App. |
| 9 | Two publication passes overlap | as cases 4–5 | n/a | either | nothing under Actions — one run at a time; only a local `--once` beside a workflow run can duplicate an evidence comment (same run marker) or, rarely, an issue | The workflow's `concurrency` group serializes runs; a further arrival replaces the single pending run, and every run sweeps all unpublished refs, so no result is dropped. After every create the publisher re-lists that fingerprint; if two open issues share it, it keeps the lowest number, comments on it, and closes the other with a pointer. |
| 10 | Same `run_id`, different content hash | `run_id` + `content_sha256` | none | none | a conflict entry on the health status; nothing published | Refused, never overwritten (§2 of the boundary document). |
| 11 | Baseline missing or all cases incomparable | n/a | n/a | n/a | evidence comment states `bootstrap` or `incomparable`; no drift issues touched | Neither opens nor resolves an issue, so it cannot cause a false open or a false close. |
| 12 | Another account posts a comment carrying a marker, or imitating the status comment | none | none | none | nothing: the comment is ignored and the real post is not suppressed | Markers and the status comment count only when the publisher identity authored them (§3); the maintainer's own account is not the publisher either. |

Manual trace: every path either ends at the seal (cases 1–2, unrecoverable by
design and visible via the watchdog), or continues from the seal by re-reading
it (cases 3–11). There is no state with a sealed result that cannot be
published, and no step whose retry can publish a second copy.

## 7. How a maintainer verifies system health

| Signal | Where | Healthy | Unhealthy → action |
| --- | --- | --- | --- |
| Routines exist, are enabled, GitHub connection alive | claude.ai/code/routines | both enabled, recent runs | disabled or disconnected → reconnect within 72 h or re-enable |
| Latest verified record per lane vs `max_gap_hours` | health status comment | within gap | overdue → missed-run issue; check Routine surface |
| Sealed but unpublished handoffs | health status; `claude/benchmark-result-*` refs | zero, or younger than a few hours | growing → publication workflow or App problem |
| Publication workflow | Actions tab; health status | enabled; scheduled sweeps succeed within the interval | stale or failing → re-enable, fix, or `workflow_dispatch`; disabled after 60 days of repository inactivity |
| Model and runtime versions | latest record `runtime.*` | as configured | unexpected → prompt spec or provider drift |
| Drift issues and `keep-open` | `benchmark-regression` label | each has a current provenance link | stale keep-open → maintainer review |
| App installation and permissions | repository → Settings → Integrations | exactly the matrix in the boundary document | broader → correct it |
| Record growth | `benchmark-history` packed size | below the §4 trigger | above → rotate or move raw |
