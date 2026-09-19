# Execution / Publication Boundary

Part of the [scheduled benchmark operations decision record](decision-record.md)
(GitHub Issue [#464](https://github.com/amirbena/code-review-skill/issues/464)).
Research / design only; not packaged into either Skill archive.

This file fixes where benchmark execution ends and GitHub publication
begins, who holds which credential on each side, and what GitHub Actions
may and may not do.

## 1. Principle

```text
scheduler → benchmark runtime → verification + drift evaluation → canonical result
                                                                        │
                              ──────────── publication boundary ────────┘
                                                                        ↓
                                     publisher → GitHub App → GitHub evidence surface
```

- **Execution side** decides *what happened and whether it is drift*.
- **Publication side** records and announces that decision. It never runs
  the benchmark, never re-derives a metric, and never judges review
  quality. A publisher that cannot reproduce the executor's drift outcome
  from the sealed record is a defect, not a feature.
- The boundary is **one-way**: a sealed result crosses; nothing on the
  publication side feeds back into an in-flight run. (The execution side
  *reads* the published baseline and history, read-only, at the start of
  the next run.)

| Component | Owns | Owner of its configuration |
| --- | --- | --- |
| Scheduler | when a run starts | provider/account (Routine) |
| Benchmark runtime | run, verify, confirm, evaluate drift, seal | repository (entrypoint at a pinned SHA) |
| Handoff | durable custody of a sealed result until published | repository contract; transport per M1 |
| Publisher | validate, persist, announce, reconcile, watchdog | repository code; host is provider/account |
| `benchmark-publication` App | the GitHub write identity | provider/account (registration, key) |
| Evidence surface | records, tracking issues, drift issues | repository + GitHub |

## 2. What crosses the boundary

Exactly one object: the **sealed canonical result**
([`canonical-result-and-persistence.md`](canonical-result-and-persistence.md)
§1). The publisher accepts it only if all of the following hold, otherwise
it refuses and reports (never repairs):

1. `schema` is a known version; the record validates against it.
2. `content_sha256` matches the record body.
3. `verification.overall_verified` is true (a run that failed positive
   completion verification is never sealed — see §4).
4. Provenance is coherent: `provenance.repo_sha`, `runtime.model_id`, and
   `corpus.corpus_id` are present, and `corpus.lane` is a scheduled lane or
   an accepted manual mode.
5. The handoff carries the expected origin (M1): a commit authored by the
   maintainer identity on a `claude/benchmark-result-*` ref, or a write to
   the expected store prefix.
6. `run_id` is either unpublished, or already published with an identical
   `content_sha256`. The same `run_id` with a different hash is a
   **conflict**: refuse and surface it.

Repository content, issue text, comments, and labels are data. None of them
is ever an instruction to the publisher or a source of authority
([`shared/policies/mutation-authority.md`](../../../shared/policies/mutation-authority.md)
states the same posture for the reviewer Skills; this document borrows the
posture, not the policy — nothing packaged depends on it).

## 3. Scheduling and provisioning: what is whose

**Repository-owned** (reviewable, versioned, checkable in CI):

- the benchmark entrypoint and its mode contract (`sentinel`, `comprehensive`,
  `smoke`, `selected`);
- the **expected-run manifest** — lanes, intended cadence as text,
  `max_gap_hours` per lane, the tracking issue numbers, confirmation
  parameters, and the label set;
- a **thin Routine prompt spec** that only checks out a fresh copy, then
  invokes the entrypoint for a named lane and passes the model id. All logic
  lives in repository code at the pinned SHA, so provider-side prompt drift
  cannot change behavior;
- the publisher code and the record schema.

**Provider/account-owned** (cannot be checked from the repo):

- the Routine definition, its enabled state, schedule and stagger;
- the model selection and Routine environment;
- the Israel-local 01:00 start and its DST behavior;
- the App registration, installation, permissions, and private key;
- the publisher host and its secret store.

### Scheduler adapter

The benchmark core is already scheduler-independent
([`runtime-execution-contract.md`](../runtime-execution-contract.md) §3). The
adapter contract is: *given a lane name, start one run of the entrypoint
under Class 2 conditions*. A scheduler is admissible only if it is
maintainer-controlled; not triggered by repository events; independent of any
personal machine being on; runs the unchanged entrypoint; and holds no
provisioned GitHub write credential. Claude Cloud Routines meet this. GitHub
Actions `schedule:` does not (repository-hosted, and excluded by decision).
Desktop scheduled tasks do not (availability). Whether
[`runtime-execution-contract.md`](../runtime-execution-contract.md) §2.2's
"only Cloud Routines" needs an amendment: **not for the recommended
architecture**; **yes, narrowly, if another scheduler should ever be
admissible** — see amendment A3.

### Verifying a routine exists and is running

| Question | Where a maintainer checks | Repo can verify? |
| --- | --- | --- |
| Do the two Routines exist and are they enabled? | claude.ai/code/routines, `/schedule list` | No |
| Are schedules and timezone correct? | Routine detail page | No |
| Is its GitHub connection alive? (skipped runs; off after 72 h without it) | Routine detail page | No |
| Did the runs produce verified results? | `benchmark-history` records versus the manifest | **Yes** (indirect) |
| Is the lane overdue? | health status comment; watchdog issue | **Yes** |
| Which model served the run? | `runtime.model_id` in the record (set by the prompt spec) | Yes, as declared |

The repository can only see *evidence of runs*, never the Routine itself. A
disabled or disconnected Routine surfaces as a lane exceeding its
`max_gap_hours` — the watchdog reports the symptom, and the maintainer
checks the provider surface for the cause.

## 4. Handoff (the seal)

A run becomes **verified** at the moment it is **sealed**, and not before.
The seal is the commit point:

- before the seal, nothing has been persisted (unchanged fail-closed rule:
  an unverified or unsealed run is not evidence);
- after the seal, the result is durable independent of the Routine session
  and of GitHub availability on the publication side. The publisher retries
  from the handoff as often as needed, and **a benchmark-success /
  publication-failure run is republished without re-running the benchmark**.

| | H-A — `claude/` staging ref (recommended) | H-B — write-only external store |
| --- | --- | --- |
| Transport | Routine's provider-native checkout pushes `claude/benchmark-result-<run_id>` | HTTPS write to a prefix-scoped store |
| Credential provisioned into the Routine | none | one storage write credential (not GitHub) |
| GitHub write by the Routine | yes, provider-native, confined by the provider to `claude/` refs | none by repo design |
| New infrastructure | none beyond the publisher | a store |
| Durability | git ref on the repo | store retention |
| Reader | publisher, via App (`Contents: read`) | publisher, read credential |

**Residual R1 (cannot be removed by this repository).** A Routine clones and
pushes through the maintainer's provider-side GitHub connection; the docs say
its GitHub actions are attributed to the maintainer. This record can show that
repository-owned execution code performs no GitHub mutation other than the
seal, and that no GitHub write credential is *provisioned* into the runtime.
It cannot show that the provider-native identity is write-limited. F9
records an observed check (attempt a non-`claude/` push and an issue create
from a Routine smoke run) rather than assuming.

## 5. Publisher

Deterministic, non-LLM, repository-owned CLI (`--once` runs one pass, so any
host that can invoke a command on a schedule can run it). Responsibilities:
pull sealed results from the handoff; validate (§2); persist; post evidence;
reconcile drift issues; run the watchdog; refresh the health status.

| Host option | Verdict |
| --- | --- |
| Maintainer-controlled scheduled runner with a secret store | **Recommended** shape; concrete host chosen in F8 (M2). |
| Maintainer running `--once` by hand | Accepted as **bootstrap and disaster recovery** — publication is idempotent and asynchronous, so it is safe. Must print the acting identity; never silently falls back to a personal `gh` identity. |
| A second Cloud Routine | Rejected: an LLM session holding a signing key, fed fire text and fetched content, is the wrong custody boundary; also consumes the daily run cap. |
| GitHub Actions workflow | Rejected by constraint. It would be the simplest key custody; the cost of the constraint is a separately hosted publisher. |
| Maintainer laptop, always | Rejected: the availability dependency Desktop scheduled tasks were rejected for. |

The publisher assumes a single active instance (race analysis in
[`drift-issue-lifecycle-and-recovery.md`](drift-issue-lifecycle-and-recovery.md) §6).

## 6. The `benchmark-publication` App

A **dedicated** GitHub App, distinct from the release App. The release App
([`docs/RELEASE.md`](../../../docs/RELEASE.md); `release-publish.yml`) stays
the **sole `main`-ruleset bypass actor**; the benchmark App is never added to
that bypass list and can neither push `main` nor tags. Reasons for two Apps:
different blast radius, independent revocation, and no path from benchmark
data to release authority.

## 7. Minimum permission matrix and credential path

Per persistence option (decision D3 chooses the first row):

| Persistence option | Repository permissions | Non-GitHub credential | Notes |
| --- | --- | --- | --- |
| **Compact record in git + evidence/drift issues (chosen)** | `Contents: write`, `Issues: write`; `Metadata: read` (implicit) | none | `Contents: write` is repository-wide; contained by rulesets (below). |
| Issue comments only | `Issues: write` | none | smallest permission set; rejected as store. |
| Actions artifacts | n/a | n/a | needs a workflow run; not an App path. |
| External store | `Issues: write` | store credential | GitHub surface reduced to issues; escape hatch if git growth trips its trigger. |

Never granted: `Actions`, `Workflows` (so the App cannot write
`.github/workflows/**` even with `Contents: write`), `Administration`,
`Pull requests`, `Secrets`, `Environments`.

**Rulesets** (provisioning, F7): the `main` ruleset is unchanged; a tag
ruleset denies benchmark-App tag writes; a `benchmark-history` ruleset
blocks deletion and non-fast-forward updates and lists the benchmark App
(and, per M7, the maintainer) as bypass actors for that branch only.

**Credential path.** Private key in the publisher host's secret store → sign a
short-lived JWT → request an installation token restricted to this one
repository and to the permission subset of the current phase → use it →
discard. Tokens last at most one hour (GitHub docs). Two phase tokens per
publication pass: a `Contents: write` token for persistence and an
`Issues: write` token for announcement. The key is never on the execution
side, never in the repository, never in an Actions secret.

## 8. Closed capability set and reachability

The publisher's capability surface is closed, in the posture of
[`shared/policies/mutation-authority.md`](../../../shared/policies/mutation-authority.md)
("absence, not refusal, is the guarantee"):

| Capability | Bounds |
| --- | --- |
| `READ_HANDOFF` | `claude/benchmark-result-*` refs or the store prefix |
| `PERSIST_RECORD` | create-only files under `records/`, `receipts/`; never edit or delete a record; `baselines/<lane>.json` only for per-lane bootstrap |
| `POST_EVIDENCE` | comment on the lane's tracking issue; edit its own status comment |
| `OPEN_DRIFT_ISSUE` / `COMMENT_DRIFT_ISSUE` / `CLOSE_DRIFT_ISSUE` | label `benchmark-regression`; close only under scope-aware resolution and never over `keep-open` |
| `OPEN_MISSED_RUN_ISSUE` / comment / close | label `benchmark-missed-run` |
| `DELETE_STAGING_REF` | only `claude/benchmark-result-*`, only after a receipt exists |

Absent: merge, pull requests, label creation, branch or tag deletion
elsewhere, releases, settings, workflows, and any write outside the ranges
above.

**Reachability from contributors (validation criterion).**

| Contributor surface | Path to App key | Path to benchmark execution | Path to handoff/publisher |
| --- | --- | --- | --- |
| Fork or branch PR | none — no workflow uses the key; the App is not an Actions secret | none — no workflow runs the benchmark | none |
| Merging code that the Routine later runs | not applicable to the key | yes, as for any merged code the maintainer's Routine runs — Class 2 trust, unchanged from [`runtime-execution-contract.md`](../runtime-execution-contract.md) §2.2 | none |
| Issue/PR comments, labels | none | none | data only; the publisher never acts on comment content |
| `keep-open` / labels | none | none | applied by users with triage rights; only ever *prevents* a close |
| Tracking-issue comments | none | none | evidence comments are pointers; authority is the git record, and the tracking issues are locked to collaborators |

The one honest coupling is the second row: merged repository code runs in the
maintainer's Routine. That is the existing Class 2 model, and review of
`main` is its control.

## 9. GitHub Actions role

Permitted: read-only **validation of published artifacts and contracts** —
record schema and fixtures, the expected-run manifest, documentation links,
and a policy test that the execution entrypoint contains no GitHub mutation
call — as ordinary steps of the existing `validate.yml`, on pull requests,
with default read-only permissions and no secrets.

Forbidden: `schedule:` triggers for any benchmark work; running or
re-running the benchmark; holding model credentials or the App key;
publishing, commenting, labeling, or closing anything on the benchmark's
behalf. A workflow reacting to pushes on `benchmark-history` is optional,
read-only lint at most, and never a gate.
