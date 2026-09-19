# Scheduled Benchmark Operations — Decision Record

Repository-development decision record for GitHub Issue
[#464](https://github.com/amirbena/code-review-skill/issues/464) (parent
[#332](https://github.com/amirbena/code-review-skill/issues/332)). Like the
rest of [`../`](../README.md), this is **not packaged into either Skill
archive**, and no packaged Skill resource depends on it.

**Status: research / design only.** Nothing here is implemented. No script,
workflow, scheduler, GitHub App, Routine, label, branch, or ruleset was
created or changed while producing it. Follow-up issues are *listed* in
[`follow-up-plan.md`](follow-up-plan.md), not created. Every conflict with
an existing contract is recorded as a proposed amendment in
[`contract-reconciliation.md`](contract-reconciliation.md) that needs
maintainer approval — no existing contract was edited.

Detail lives in the sibling documents; this file holds the evidence, the
decisions, and what still needs a maintainer's choice.

## 1. The architecture constraint this record is built on

The fixed requirement: GitHub Actions must **never schedule, execute,
re-execute, or evaluate the benchmark**. Execution happens outside GitHub,
produces a sealed canonical result, and only then does GitHub enter — through
a publication-only identity. Whether Actions may deterministically *publish* an
already sealed result is a separate question; it is answered by verified
evidence in [`publication-architecture.md`](publication-architecture.md), not
by the requirement above.

```text
EXECUTION SIDE  (outside GitHub; no GitHub write credential is provisioned into it)
  Claude Cloud Routine  |  admissible external scheduler   (scheduler adapter)
    → benchmark runtime            (repo entrypoint at a pinned SHA)
    → verification                 (existing positive completion check)
    → drift evaluation             (baseline read-only; confirmation re-runs)
    → canonical result             (sealed, schema-versioned, content-hashed)
    → handoff                      (sealed `claude/benchmark-result-<run_id>` ref —
                                    the seal is one bounded provider-mediated write)
─────────────────── one-way publication boundary ───────────────────
PUBLICATION SIDE  (deterministic; never judges; never executes the benchmark)
  publication-only GitHub Actions workflow   (default-branch definition;
                                              `schedule` sweep + manual `workflow_dispatch`)
    → benchmark-publication GitHub App token (minted inside the job)
    → persist record   → post run evidence   → reconcile drift issues
    → missed-run watchdog / health status
GITHUB  (evidence surface)
  `benchmark-history` branch · tracking issues · drift issues
```

The App executes a publication plan derived from an already-determined
result. It does not run the benchmark and does not decide whether review
quality drifted. Boundary specification:
[`execution-publication-boundary.md`](execution-publication-boundary.md).

## 2. Current state (verified 2026-09-19)

Each row can be re-checked with the command shown.

| # | Claim | Evidence / re-check |
| --- | --- | --- |
| E1 | No `benchmark-history` branch exists on `origin`; only `main`. | `git ls-remote --heads origin` |
| E2 | Labels `benchmark-regression` and `keep-open` are not defined in the repository. They are referenced only by [`benchmark_drift.py`](../scripts/benchmark_drift.py) (`REGRESSION_LABEL`, `KEEP_OPEN_LABEL`). | `gh label list --limit 100` |
| E3 | No benchmark evidence tracking issue exists (only #464 and unrelated issues matched an evidence search). | `gh issue list --search "benchmark evidence" --state all` |
| E4 | The only scheduling artifact in the repo is a prompt template inside [`cloud-routine-integration.md`](../../../docs/benchmark/cloud-routine-integration.md) §9; no Routine definition is verifiable from the repo. | file inspection |
| E5 | Persistence is described two ways: evidence-issue comments, with repository commits rejected ([`cloud-routine-integration.md`](../../../docs/benchmark/cloud-routine-integration.md) §4), versus a `benchmark-history` branch ([`nightly-history-and-baseline.md`](../nightly-history-and-baseline.md) §3). | file inspection |
| E6 | History entries are keyed `<date>-<repo_sha[:12]>` per lane and `record_run` refuses to overwrite ([`benchmark_history.py`](../scripts/benchmark_history.py) `HistoryEntry.filename`, `record_run`). Two runs of one lane on one SHA and UTC day collide; the second cannot be recorded. | `record_run` |
| E7 | Retention prunes files from the working tree only ([`benchmark_history.py`](../scripts/benchmark_history.py) `_prune_history`); git history keeps every pruned entry, so the "newest 90" rule does not bound repository size. | `_prune_history` |
| E8 | Publication uses the maintainer's `gh` identity inside the Routine ([`run_benchmark_routine.py`](../scripts/run_benchmark_routine.py) `_gh`, `_post_evidence`; [`runtime-execution-contract.md`](../runtime-execution-contract.md) §2.2). The same process runs the model-backed benchmark. | file inspection |
| E9 | `--results-out` is written before the evidence post; a failed post raises and exits non-zero, so the documented history step (step 5, which step 4 skips whenever step 3 exits non-zero) never runs for a run that already verified. | [`run_benchmark_routine.py`](../scripts/run_benchmark_routine.py) `run_benchmark_mode`; [`nightly-history-and-baseline.md`](../nightly-history-and-baseline.md) §2 |
| E10 | The evidence marker is a constant (`EVIDENCE_MARKER`); a retried post appends a second comment, and an omitted `--evidence-issue` creates a new issue on every call. | `_post_evidence` |
| E11 | No Routine step calls `benchmark_drift.py`, and nothing derives its `--baseline-file`/`--candidate-file` inputs from history; the CLI expects a caller to pre-compute them (`_load_case_metrics_and_severity` docstring). | [`benchmark_drift.py`](../scripts/benchmark_drift.py) |
| E12 | A single observation is sufficient to open a drift issue; the "confirmed drift" of [`runtime-execution-contract.md`](../runtime-execution-contract.md) §2.2 has no defined meaning. | `classify_drift`, `sync_regressions` |
| E13 | **`sync_regressions` closes any open `benchmark-regression` issue whose fingerprint is absent from the current drift set, regardless of lane.** Demonstrated in a scratch run (no repo change): an open issue for a comprehensive-only case is closed by a sentinel sync with zero drift records. Contradicts [`drift-detection-and-regression-lifecycle.md`](../drift-detection-and-regression-lifecycle.md) §7's "no cross-lane" verification, which holds for `compare()` but not for the issue lifecycle. | [`benchmark_drift.py`](../scripts/benchmark_drift.py) `sync_regressions` (lists every open labeled issue, then closes each fingerprint absent from the current set) |
| E14 | The comprehensive `corpus_id` digests every discovered fixture's path and content ([`benchmark_history.py`](../scripts/benchmark_history.py) `comprehensive_corpus_digest`), and `compare()` raises on any `corpus_id` mismatch ([`benchmark_report.py`](../reference/benchmark_report.py)). The corpus tree changed in 41 commits in the 31 days to 2026-09-19. A pinned comprehensive baseline (promoted only by explicit maintainer action) will therefore mismatch after almost any corpus PR. | `git log --since="2026-08-19" --oneline -- docs/benchmark/corpus \| wc -l` |
| E15 | Comprehensive membership is currently **106** `benchmark-case/v2` fixtures (derived by `discover_comprehensive_fixtures`), not the "~89" in #431's text. Informational: membership is derived, never hard-coded. | [`benchmark_corpus_membership.py`](../scripts/benchmark_corpus_membership.py) |
| E16 | The `main` branch has an active repository ruleset (deletion, non-fast-forward, pull request, required status checks). Its live bypass actors are the **Admin role and the release App**; [`docs/RELEASE.md`](../../../docs/RELEASE.md) documents the App only. There is no benchmark-publication App, and no other ruleset (no tag ruleset). | `gh api repos/amirbena/code-review-skill/rulesets` and `.../rulesets/20558650` |
| E17 | No workflow in `.github/workflows/` references the benchmark; there is no Actions benchmark path ([#420](https://github.com/amirbena/code-review-skill/issues/420)). | `grep -rn benchmark .github/workflows/` |
| E18 | Actions configuration: default `GITHUB_TOKEN` permissions are read-only; fork-PR runs need approval for first-time contributors; the only collaborator is `amirbena` (admin); the `release` environment has no protection rules and no branch policy and holds `RELEASE_APP_ID` / `RELEASE_APP_PRIVATE_KEY`. | `gh api repos/amirbena/code-review-skill/actions/permissions/workflow`, `.../actions/permissions/fork-pr-contributor-approval`, `.../collaborators`, `.../environments`; `gh secret list --env release` |
| E19 | No workflow listens for pushes to `claude/*` refs and no push-triggered run exists on such refs, so there is **no observed data** on whether a Routine's push fires a workflow. | `gh api "repos/amirbena/code-review-skill/actions/runs?event=push&per_page=100"` |
| E20 | The repository activity API attributes a ref creation to its actor and resulting SHA server-side (verified on this repository). | `gh api "repos/amirbena/code-review-skill/activity?activity_type=branch_creation"` |

### Provider facts relied on

- **Routines** ([Claude Code docs — routines](https://code.claude.com/docs/en/routines);
  research preview, subject to change): schedule times are entered in the
  user's local zone and converted; a run can start a few minutes late
  because of a per-routine stagger; presets are hourly, daily, weekdays and
  weekly, with custom cron via `/schedule update` and a one-hour minimum
  interval; anything a routine does through the connected GitHub identity is
  attributed to the maintainer; pushes to `claude/`-prefixed branches are
  always accepted, while pushes to other branches are rejected if protected;
  a routine skips runs while its GitHub connection is missing and turns off
  after 72 hours; runs count against a daily per-account cap; a green run
  status means only that the session exited without an infrastructure error,
  not that the task succeeded; environment variables are visible to anyone
  who uses the environment. The page states no per-run duration limit
  and no explicit DST behavior — both are **unverified** here. For cloud
  sessions generally, git credentials stay outside the sandbox and a proxy
  authenticates with scoped credentials
  ([cloud sessions](https://code.claude.com/docs/en/claude-code-on-the-web));
  what scope the proxy grants is not stated.
- **GitHub Apps** ([installation access tokens](https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/generating-an-installation-access-token-for-a-github-app),
  [permissions required](https://docs.github.com/en/rest/authentication/permissions-required-for-github-apps)):
  installation tokens expire after 1 hour and can be narrowed to named
  repositories and a subset of permissions at creation; issues, comments and
  labels require `Issues: write`; git refs and contents require
  `Contents: write`.
- **Size and retention** ([large files](https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-large-files-on-github),
  [artifacts](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/download-workflow-artifacts)):
  git warns above 50 MiB, GitHub blocks files above 100 MiB, repositories
  are ideally under 1 GB; artifacts and logs are stored for 90 days by
  default and are tied to workflow runs.
- **GitHub Actions** — token identity, trigger and ref semantics, ruleset
  bypass, re-run and concurrency behavior, and the activity API are cited row
  by row in [`publication-architecture.md`](publication-architecture.md) §2.
- **Issue-comment length**: the API rejects bodies over 65,536 characters
  (HTTP 422). This is *not* stated on the REST pages fetched for this
  record; it is community-reported, so treat it as an unofficial figure.

## 3. Decisions

| ID | Decision | Detail |
| --- | --- | --- |
| D1 | **Execution/publication boundary.** Execution, verification and drift evaluation happen outside GitHub and end in a sealed canonical result. GitHub is entered only afterwards, only through the publication App, one-way. *Unchanged.* | [`execution-publication-boundary.md`](execution-publication-boundary.md) §1–§2 |
| D2 | **Scheduler.** Claude Cloud Routine remains the default scheduler behind a scheduler-adapter boundary; the core stays scheduler-independent. GitHub Actions as a benchmark scheduler or runner, and Desktop scheduled tasks, stay rejected. §2.2 needs an *optional* narrow amendment (an admissibility test) to allow another scheduler, and none for the recommended architecture itself. | [`execution-publication-boundary.md`](execution-publication-boundary.md) §3; [`contract-reconciliation.md`](contract-reconciliation.md) A3 |
| D3 | **Persistence.** A bounded combination: a compact, schema-versioned, content-hashed record per run in git on `benchmark-history` (authoritative), a per-run evidence comment on a per-lane tracking issue (index and notification, not the store), and a time-bounded raw bundle in the handoff. Not every run's raw output goes in git; an issue comment is never the store. | [`canonical-result-and-persistence.md`](canonical-result-and-persistence.md) |
| D4 | **Handoff.** A run is *verified* only once it is **sealed** into a durable handoff; publication is retried from the handoff and never re-runs the benchmark. Recommended transport: a `claude/`-prefixed staging ref written with the Routine's provider-native checkout transport. No GitHub write credential is *provisioned* into the runtime; the seal itself is one bounded, provider-mediated GitHub write. Alternative: a write-only external store. | [`execution-publication-boundary.md`](execution-publication-boundary.md) §4 |
| D5 | **Publisher.** A deterministic, non-LLM, repo-owned CLI run by a **publication-only GitHub Actions workflow** (default-branch definition; `schedule` sweep plus manual `workflow_dispatch`). Correctness never depends on an arrival event. A maintainer-run `--once` is the disaster-recovery path. No external host. *Changed by the final pass.* | [`publication-architecture.md`](publication-architecture.md) §2–§7 |
| D6 | **App identity.** A dedicated `benchmark-publication` GitHub App, distinct from the release App, whose installation token is minted **inside the publication job** with per-phase minimum permissions; `GITHUB_TOKEN` is limited to `contents: read`. The App is what makes a single-writer ruleset on `benchmark-history` possible. *Changed by the final pass.* | [`publication-architecture.md`](publication-architecture.md) §2 (finding 6), §4; [`execution-publication-boundary.md`](execution-publication-boundary.md) §6–§8 |
| D7 | **Drift → issue.** Evaluation stays in the benchmark (#339 classification and fingerprint unchanged). Issue-worthy means *confirmed* drift (in-run confirmation re-runs); resolution is scoped to the lanes that cover the case; recurrence after closure opens a new linked issue; new issues per run are capped. | [`drift-issue-lifecycle-and-recovery.md`](drift-issue-lifecycle-and-recovery.md) §1–§4 |
| D8 | **Failure and recovery.** Idempotency is `run_id` plus markers on GitHub objects; the receipt is derived, never authoritative. A gap-based watchdog — the scheduled trigger of the same publication workflow — detects missed runs without any timezone logic. *Watchdog ownership changed by the final pass.* | [`drift-issue-lifecycle-and-recovery.md`](drift-issue-lifecycle-and-recovery.md) §5–§7; [`publication-architecture.md`](publication-architecture.md) §6 |
| D9 | **GitHub Actions role.** Permitted: the publication-only workflow (D5) and read-only validation of repo-owned contracts. Forbidden: scheduling, running, re-running, or evaluating the benchmark; model or provider credentials; consuming issue, PR, or comment text as instructions. *Changed by the final pass.* | [`publication-architecture.md`](publication-architecture.md) §5; [`execution-publication-boundary.md`](execution-publication-boundary.md) §9 |

### Rejected alternatives (summary)

| Alternative | Rejected because | Where |
| --- | --- | --- |
| GitHub Actions scheduling or running the benchmark | It would need a provider credential in a repository-hosted, contributor-adjacent runtime — the Class 1 shape whose candidates failed the viability bar ([`runtime-execution-contract.md`](../runtime-execution-contract.md) §2.1, §8; [#336](https://github.com/amirbena/code-review-skill/issues/336)/[#366](https://github.com/amirbena/code-review-skill/issues/366)) — and it is the fixed requirement. | publication §1 |
| **A — external publisher host + App** | No guarantee that publication-only Actions cannot preserve; it adds hosting, deployment, a secret store, availability monitoring, and its own polling. | publication §7 |
| **B1 — privileged workflow on `push`/`create` of the staging ref** | A push-triggered job runs the definition carried by the pushed ref, so the ref holding the sealed result would also hold the code that receives the credential. | publication §2 (finding 2), §3 |
| `GITHUB_TOKEN`-only publication | It cannot be a ruleset bypass actor, so `benchmark-history` could not be single-writer; its identity is the shared Actions identity. | publication §2 (findings 5–6) |
| Arrival-event trigger as the *only* trigger | Unproven for a Routine push (E19), and cannot detect an absent result. Kept as an optional accelerator (F16). | publication §3, §6 |
| Claude Desktop scheduled tasks | Personal-machine availability dependency ([`runtime-execution-contract.md`](../runtime-execution-contract.md) §7). | boundary §3 |
| A second Routine as publisher or watchdog | An LLM session holding a GitHub write path, capped by the daily run allowance. | publication §6 |
| Maintainer `gh` identity for publication | Not least-privilege or independently revocable. | boundary §6 |
| Actions artifacts as the store | 90-day default retention; tied to workflow runs; not addressable by commit. | persistence §2 |
| Issue comments as the store | Editable, length-capped, unschematized, paginated for baseline reads. | persistence §2 |
| Raw per-run output in git | Growth is unbounded because git retains pruned history (E7). | persistence §4 |
| Cross-run debounce as the only confirmation | Delays a real regression by two full cycles (6 days sentinel, 14 days comprehensive). | drift §2 |

## 4. Decisions that need a maintainer

These are recommendations, not settled. Each blocks or shapes a follow-up.

| ID | Question | Recommendation |
| --- | --- | --- |
| M1 | Handoff transport: `claude/` staging ref (no GitHub write credential provisioned; the seal is a bounded provider-mediated write) or a write-only external store (no GitHub write at all from the Routine; new infrastructure and a secret)? | Staging ref. Choose the external store only if a zero-GitHub-write Routine is a hard requirement. |
| M2 | Publication trigger, and the "no GitHub Actions cron" wording (A13). | Approve A13. Publication-only `schedule` sweep (recommended every 2 hours) plus manual `workflow_dispatch`; defer the `workflow_run` arrival accelerator (F16). |
| M3 | Confirmation parameters (re-runs per drifting case, threshold, cap on cases confirmed per run). | 2 re-runs, ≥ 2 of 3 observations, cap 10. |
| M4 | Comprehensive lane comparability: per-case `fixture_digest` so a fixture edit downgrades only that case (E14), versus total fail-closed plus a re-promotion ritual. | Per-case comparability (A7 — the highest-consequence amendment). |
| M5 | Cadence wording: "every 3 days" is not expressible as an exact cron interval, and "Friday night" at 01:00 is ambiguous (Thursday night versus Friday night). | Bound by maximum gap (sentinel ≤ 96 h, comprehensive ≤ 8 d); state the local weekday explicitly. |
| M6 | Amend §2.2's "Cloud Routines only" into an admissibility test? | Yes, narrowly (A3). Not needed to proceed. |
| M7 | Baseline promotion mechanism under the App-only branch ruleset. | The maintainer promotes with their own credentials (ruleset bypass for that branch only); the publisher performs only per-lane bootstrap. |
| M8 | One evidence comment per run, or a single edited status comment plus comments only on non-clean runs? | Per-run comment; revisit if volume becomes noise. |

## 5. Acceptance-criteria trace

| Criterion | Satisfied by |
| --- | --- |
| Contract-first decision record covering all five areas, with repository evidence and official GitHub docs | this file §2–§3; the sibling documents |
| Persistence comparison and every schema field named | [`canonical-result-and-persistence.md`](canonical-result-and-persistence.md) §2–§3 |
| Per-option minimum permissions; benchmark runtime holds no provisioned write credential | [`publication-architecture.md`](publication-architecture.md) §4–§5; [`execution-publication-boundary.md`](execution-publication-boundary.md) §6–§8 |
| Publication architecture chosen on verified GitHub behavior, not on a constraint | [`publication-architecture.md`](publication-architecture.md) §2, §7 |
| Failure table with idempotency key and retry boundary; republish without re-run | [`drift-issue-lifecycle-and-recovery.md`](drift-issue-lifecycle-and-recovery.md) §6 |
| Conflicts as an explicit amendment list; follow-ups listed, not created | [`contract-reconciliation.md`](contract-reconciliation.md); [`follow-up-plan.md`](follow-up-plan.md) |
