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
| Publisher | validate, persist, announce, reconcile, watchdog | repository code, run by a publication-only Actions workflow ([`publication-architecture.md`](publication-architecture.md)) |
| `benchmark-publication` App | the GitHub write identity | provider/account (registration; key held as environment secrets) |
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
5. The handoff carries the expected origin (M1). For the staging ref: the
   repository activity API reports a `branch_creation` of that exact ref, at
   the fetched SHA, by an actor in the manifest's pusher allowlist — commit
   author metadata is never used, and unavailable attribution refuses
   ([`publication-architecture.md`](publication-architecture.md) §2, finding 4).
   For an external store: a write under the expected prefix.
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
- the publisher CLI, the publication workflow, and the record schema.

**Provider/account-owned** (cannot be checked from the repo):

- the Routine definition, its enabled state, schedule and stagger;
- the model selection and Routine environment;
- the Israel-local 01:00 start and its DST behavior;
- the App registration, installation, permissions, and private key;
- the `benchmark-publication` environment's secrets and branch policy.

### Scheduler adapter

The benchmark core is already scheduler-independent
([`runtime-execution-contract.md`](../runtime-execution-contract.md) §3). The
adapter contract is: *given a lane name, start one run of the entrypoint
under Class 2 conditions*. A scheduler is admissible only if it is
maintainer-controlled; not triggered by repository events; independent of any
personal machine being on; runs the unchanged entrypoint; and holds no
provisioned GitHub write credential. Claude Cloud Routines meet this. GitHub
Actions as a *benchmark* scheduler does not (it would need a provider credential
in a repository-hosted runtime; a publication-only Actions schedule is a
different thing — see §5).
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
  and of the publication side. Publication retries from the handoff as often
  as needed, and **a benchmark-success / publication-failure run is
  republished without re-running the benchmark**.

| | H-A — `claude/` staging ref (recommended) | H-B — write-only external store |
| --- | --- | --- |
| Transport | Routine's provider-native checkout pushes `claude/benchmark-result-<run_id>` | HTTPS write to a prefix-scoped store |
| Credential provisioned into the Routine | none | one storage write credential (not GitHub) |
| GitHub write by the Routine | yes — the seal, provider-mediated, confined by the provider to `claude/` refs | none by repo design |
| New infrastructure | none | a store |
| Durability | git ref on the repo | store retention |
| Reader | publication job (`GITHUB_TOKEN`, `contents: read`) | publication job, read credential |

**The precise guarantee, and residual R1.** *No GitHub write credential is
provisioned into the benchmark runtime, and repository-owned execution code
performs no GitHub mutation other than the seal.* The seal itself is a bounded
GitHub write mediated by the provider: a Routine clones and pushes through the
maintainer's provider-side GitHub connection, its git credentials stay outside
the sandbox behind a proxy that authenticates with scoped credentials, and its
GitHub actions are attributed to the maintainer. This repository cannot show
what scope that proxy credential has. F9 records an observed check (attempt a
non-`claude/` push and an issue create from a Routine smoke run) rather than
assuming.

## 5. Publisher

A deterministic, non-LLM, repository-owned CLI with a `sweep` subcommand
(validate, persist, announce, and reconcile **every** unpublished sealed ref,
processed in ascending `sealed_at`), a `watchdog` subcommand, and a `--once`
mode for local runs. It is executed by a **publication-only GitHub Actions
workflow**; the comparison with an external host, the verified GitHub behavior,
and the workflow's incapabilities are in
[`publication-architecture.md`](publication-architecture.md).

| Where it runs | Verdict |
| --- | --- |
| **Publication-only Actions workflow** — default-branch definition; `schedule` sweep plus manual `workflow_dispatch` | **Chosen.** No host, deployment path, or separate secret store; native serialization; the run URL goes in the receipt. |
| Maintainer running `--once` by hand | Accepted as **bootstrap and disaster recovery** — publication is idempotent and asynchronous. Must print the acting identity; never falls back to a personal `gh` identity. |
| External scheduled host holding the App key (option A) | Rejected: it preserves no guarantee the workflow cannot, and adds hosting, deployment, a secret store, and monitoring. |
| Privileged workflow on `push`/`create` of the staging ref (B1) | Rejected: it runs the definition carried by the ref it processes. |
| A second Cloud Routine | Rejected: an LLM session holding a GitHub write path. |
| Maintainer laptop, always | Rejected: the availability dependency Desktop scheduled tasks were rejected for. |

Serialization is the workflow's `concurrency` group; a local `--once` running
at the same moment is the operator's responsibility (race analysis in
[`drift-issue-lifecycle-and-recovery.md`](drift-issue-lifecycle-and-recovery.md) §6).

## 6. The `benchmark-publication` App

A **dedicated** GitHub App, distinct from the release App. The release App
([`docs/RELEASE.md`](../../../docs/RELEASE.md); `release-publish.yml`) stays the
only *App* on the `main` ruleset's bypass list (the live ruleset also lists the
Admin role — evidence E16); the benchmark App is never added to it and can
neither push `main` nor tags. Reasons for two Apps: different blast radius,
independent revocation, and no path from benchmark data to release authority.
Using the App token inside the publication job — rather than `GITHUB_TOKEN`
alone — is what allows a single-writer `benchmark-history` ruleset and an
attributable identity ([`publication-architecture.md`](publication-architecture.md) §2, finding 6).

## 7. Minimum permission matrix and credential path

Per persistence option (decision D3 chooses the first row):

| Persistence option | Repository permissions | Non-GitHub credential | Notes |
| --- | --- | --- | --- |
| **Compact record in git + evidence/drift issues (chosen)** | `Contents: write`, `Issues: write`; `Metadata: read` (implicit) | none | `Contents: write` is repository-wide; contained by rulesets. |
| Issue comments only | `Issues: write` | none | smallest permission set; rejected as store. |
| Actions artifacts | n/a | n/a | written from a workflow run, not an App path; rejected on retention. |
| External store | `Issues: write` | store credential | GitHub surface reduced to issues; escape hatch if git growth trips its trigger. |

Never granted: `Actions`, `Workflows` (so the App cannot write
`.github/workflows/**` even with `Contents: write`), `Administration`,
`Pull requests`, `Secrets`, `Environments`.

**Rulesets** (provisioning, F7): the per-ref table is in
[`publication-architecture.md`](publication-architecture.md) §4 — `main`
unchanged with the benchmark App never a bypass actor; a tag ruleset; a
single-writer `benchmark-history` ruleset; deletion and force-push protection on
sealed staging refs, with creation and update left open for the provider's push.

**Credential path.** The App ID and private key are secrets of a dedicated
`benchmark-publication` environment whose deployment branch policy is the
default branch only. The publication job mints two installation tokens with
`actions/create-github-app-token`, each restricted to this repository and to one
permission (`contents: write`, then `issues: write`), uses them, and they are
revoked at job end; a token lives at most one hour (GitHub docs). The job's own
`GITHUB_TOKEN` is `contents: read`. The key is never on the execution side and
never in the repository.

## 8. Closed capability set and reachability

The publisher's capability surface is closed, in the posture of
[`shared/policies/mutation-authority.md`](../../../shared/policies/mutation-authority.md)
("absence, not refusal, is the guarantee"):

| Capability | Bounds |
| --- | --- |
| `READ_HANDOFF` | `claude/benchmark-result-*` refs, or the store prefix |
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
| Fork or branch PR | none — the key is an environment secret gated to the default branch; a PR or branch workflow cannot read it | none — no workflow runs the benchmark | none — the publication triggers are `schedule` and `workflow_dispatch` on the default-branch definition |
| Pushing a `claude/…` ref | none | none | requires write access (E18: one collaborator); the sweep publishes only a ref whose activity attribution, name, and record validate |
| Merging code that the Routine later runs | not applicable to the key | yes, as for any merged code the maintainer's Routine runs — Class 2 trust, unchanged from [`runtime-execution-contract.md`](../runtime-execution-contract.md) §2.2 | none |
| Issue/PR comments, labels | none | none | data only; the publisher never acts on comment content |
| `keep-open` / labels | none | none | applied by users with triage rights; only ever *prevents* a close |
| Tracking-issue comments | none | none | evidence comments are pointers; authority is the git record, and the tracking issues are locked to collaborators |

The one honest coupling is the third row: merged repository code runs in the
maintainer's Routine. That is the existing Class 2 model, and review of
`main` is its control. The publication workflow's own definition is also merged
code — the same control applies, and its incapabilities are enforced by a
policy test ([`publication-architecture.md`](publication-architecture.md) §5).

## 9. GitHub Actions role

**Permitted:**

1. the **publication-only workflow** of §5 — sealed-result publication and the
   missed-run watchdog, with the guarantees in
   [`publication-architecture.md`](publication-architecture.md) §5;
2. read-only **validation of published artifacts and contracts** — record
   schema and fixtures, the expected-run manifest, documentation links, and the
   policy tests that keep both the execution entrypoint and the publication
   workflow within their bounds — as ordinary steps of `validate.yml`, with
   default read-only permissions and no secrets.

**Forbidden:** scheduling, running, re-running, or evaluating the benchmark;
holding model, Claude, or provider credentials; consuming issue, PR, or comment
text as instructions; changing a sealed result; any workflow triggered by
events on `benchmark-history` or on staging refs.
