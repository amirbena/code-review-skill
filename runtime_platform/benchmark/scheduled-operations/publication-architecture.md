# Publication Architecture: External Publisher vs Publication-Only Actions

Part of the [scheduled benchmark operations decision record](decision-record.md)
(GitHub Issue [#464](https://github.com/amirbena/code-review-skill/issues/464)).
Research / design only; not packaged into either Skill archive.

This is the final refinement pass on one question the earlier record answered
circularly: **who runs publication once a sealed result exists?** It replaces
the earlier reasoning that rejected GitHub Actions as publisher "by
constraint".

## 1. The fixed requirement, stated narrowly

GitHub Actions must **never schedule, execute, re-execute, or evaluate the
benchmark**. That is the whole requirement. It does not follow that Actions
cannot deterministically publish an already sealed canonical result, so the
two options below are compared on evidence, not on the earlier constraint.

```text
A — external publisher
  Routine → run / verify / drift evaluation → sealed handoff
    → external deterministic publisher → benchmark-publication App → GitHub

B — publication-only GitHub Actions
  Routine → run / verify / drift evaluation → sealed `claude/benchmark-result-<run_id>` ref
    → deterministic publication-only workflow → GitHub
```

Option B, wherever it is triggered, must be **incapable** of: running or
re-running the benchmark; invoking the model or runtime; evaluating review
quality; deriving drift; changing the sealed result; or consuming issue, PR, or
comment text as instructions. It only validates a sealed record and executes
the publication plan already determined in it. Enforcement is structural
(§3, §5), not a request.

## 2. Verification against real GitHub behavior

Every row cites where it was checked. "Repo" means a read-only query of this
repository on 2026-09-19. Nothing was created to test behavior: no ref, workflow,
App, or environment. Where a property is therefore *expected but not
demonstrated*, the row says so.

| # | Question | Finding | Evidence | Consequence |
| --- | --- | --- | --- | --- |
| 1 | Does the provider-native push that creates `claude/benchmark-result-<run_id>` reliably trigger a workflow? | **Expected, not demonstrated for a Routine push.** Only events created with `GITHUB_TOKEN` are suppressed (exceptions: `workflow_dispatch`, `repository_dispatch`). A cloud session pushes through a proxy with scoped credentials and its GitHub activity is attributed to the maintainer; the docs warn that a reply Claude posts as the maintainer can trigger `issue_comment` workflows, so provider-mediated activity is not a `GITHUB_TOKEN` event. Repo: no workflow listens to pushes on `claude/*` and no historical push runs exist on such refs, so there is no observed data. | [Triggering a workflow](https://docs.github.com/en/actions/using-workflows/triggering-a-workflow); [cloud sessions](https://code.claude.com/docs/en/claude-code-on-the-web) (security and auto-fix sections); repo run listing | Correctness must **not** depend on an arrival event. A periodic sweep is the trigger of record; an event is at most a latency accelerator. |
| 2 | Which event, and how narrowly scoped? | `push` with `branches: ['claude/benchmark-result-*']` (`*` does not cross `/`, and a `run_id` has none), or `create`. Branch deletion is a separate `delete` event and does not fire `push` workflows, so the publisher's own staging-ref deletion cannot re-trigger it. **But** a push-triggered workflow runs the definition carried by the pushed commit, which the docs say includes workflows not yet merged into the default branch. | [Events that trigger workflows](https://docs.github.com/en/actions/writing-workflows/choosing-when-your-workflow-runs/events-that-trigger-workflows) | A *privileged* job directly on `push`/`create` would be defined by the very ref it processes: rejected (B1). The safe event shape is an unprivileged trigger plus a `workflow_run` job, whose definition is read from the default branch and which may access secrets (B2). |
| 3 | Can contributor-controlled refs or PR activity reach the path? | Not through B′. Creating a `claude/…` ref requires push access to the base repository (a fork PR creates no base ref). Repo: the only collaborator is `amirbena` (admin); fork-PR runs require approval for first-time contributors; default workflow permissions are read-only. B′'s `schedule` trigger executes the default-branch definition; `workflow_dispatch` executes the selected ref's copy and needs write access, and the environment's `main`-only deployment policy withholds the App key from a non-`main` ref. No trigger or parameter carries issue, PR, or comment text. | repo collaborators, `actions/permissions`, `actions/permissions/workflow`; the events page above | Reach requires write access, i.e. the maintainer's own trust level (Class 2). Dispatch inputs are still validated as data. |
| 4 | Can the workflow verify the handoff origin before granting mutation authority? | **Yes, server-side.** The repository activity API returns, per ref, the activity type, the actor, and the resulting SHA — verified here (e.g. a `branch_creation` by `amirbena` for a named ref with its SHA). Commit author fields are arbitrary git metadata and are **not** used. The publisher requires `activity_type = branch_creation`, `ref` matching the pattern, `actor.login` in the manifest's pusher allowlist, and `after` equal to the fetched tip, then the record checks. The docs do not state the endpoint's permission requirement or retention: if the attribution is unavailable the sweep **refuses** (fail closed), and the maintainer accepts a specific `run_id` by dispatching it — an authenticated write-access act. | repo activity query; [List repository activities](https://docs.github.com/en/rest/repos/repos#list-repository-activities) | Origin authority does not rely on the sealed content or on commit metadata. |
| 5 | Is `GITHUB_TOKEN` sufficient, and what identity do mutations receive? | Technically sufficient (`contents: write`, `issues: write`). It is an installation token of the GitHub Actions app, scoped to this repository and the job's `permissions`; mutations carry that shared identity, indistinguishable from any other workflow's. Its writes do not trigger workflows. It is **not** in the ruleset bypass list (roles, teams, GitHub Apps, Dependabot), and this repository's own release workflow records that it cannot bypass the ruleset. | [GITHUB_TOKEN](https://docs.github.com/en/actions/concepts/security/github_token); [creating rulesets](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/creating-rulesets-for-a-repository); `release-publish.yml` | With `GITHUB_TOKEN` alone, `benchmark-history` cannot be restricted to a single writer. |
| 6 | Does a dedicated App token inside the job materially help? | **Yes, four ways.** (a) *Ruleset isolation*: the App can be the sole bypass actor of a "restrict updates" rule on `benchmark-history`; `GITHUB_TOKEN` cannot. (b) *Identity*: `benchmark-publication[bot]` is attributable; `github-actions[bot]` is not. (c) *Revocation*: uninstall the App or rotate its key without editing a workflow. (d) *Least privilege*: `permission-*` and `repositories` inputs narrow each token, and it is revoked at job end and lives at most one hour. Costs: two secrets in an environment; App-token writes **do** trigger workflows (none listens to `benchmark-history`, and the guard test in §5 enforces that); one first-party action, already used by the release workflow. | [`actions/create-github-app-token`](https://github.com/actions/create-github-app-token); [installation tokens](https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/generating-an-installation-access-token-for-a-github-app) | Keep the dedicated App (D6). Use it inside the job; `GITHUB_TOKEN` is limited to `contents: read`. |
| 7 | Exact permissions | See §4. | [permissions required](https://docs.github.com/en/rest/authentication/permissions-required-for-github-apps) | |
| 8 | Ruleset implications | See §4. | [available rules](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets) | |
| 9 | Retry/replay after a halfway failure | Actions never retries on its own. A failed run can be re-run for 30 days (at most 50 times) but a re-run keeps the original commit and the original triggering actor's privileges, so it replays *old* workflow code. Design: the sweep is **stateless** — every run processes every sealed ref that lacks a complete publication — so the next scheduled run heals any earlier failure, and a fresh `workflow_dispatch` is preferred over a re-run. | [Re-running workflows](https://docs.github.com/en/actions/managing-workflow-runs-and-deployments/managing-workflow-runs/re-running-workflows-and-jobs) | Automatic retry latency is one sweep interval; no host is needed for it. |
| 10 | Can a manual publication-only dispatch give disaster recovery without re-execution? | **Yes.** `workflow_dispatch` on `main` runs the default-branch definition (a dispatch on another ref runs that ref's copy, which the environment's `main`-only deployment policy denies the App key), needs write access, and takes an optional `run_id` (validated against the `run_id` pattern) and `dry_run`. It publishes from existing sealed refs only and has no path to the benchmark. If Actions itself is unavailable, the same CLI runs locally (`--once`) under the App key, printing the acting identity; it never falls back to a personal `gh` identity. | events page; the CLI contract in the boundary document | DR needs no separate host or procedure beyond one CLI. |
| 11 | Concurrency of two close-together sealed results | A workflow-level `concurrency` group (`cancel-in-progress: false`) runs one at a time; a further arrival replaces the single *pending* run, and ordering is not guaranteed. This is harmless **because each run sweeps all unpublished sealed refs**, processed in ascending `sealed_at`. The same group serializes the watchdog and publication. | [Concurrency](https://docs.github.com/en/actions/writing-workflows/choosing-what-your-workflow-does/control-the-concurrency-of-workflows-and-jobs) | Stronger than the external design's "assume a single instance": GitHub enforces serialization. A concurrently running local `--once` is still the operator's responsibility. |
| 12 | Are `run_id + content_sha256` and the GitHub-object markers still enough? | **Yes, unchanged.** Persist stays create-only and hash-checked; markers on comments and issues stay the idempotency authority; the receipt stays derived. Actions adds one fact: `publisher_run_url` (the workflow run) in the receipt. | [`canonical-result-and-persistence.md`](canonical-result-and-persistence.md) §1; [`drift-issue-lifecycle-and-recovery.md`](drift-issue-lifecycle-and-recovery.md) §3, §6 | No change to the failure table's guarantees. |

## 3. Trigger shapes considered

| Shape | Definition executed | Verdict |
| --- | --- | --- |
| **B1** — privileged job on `push` / `create` of the staging ref | the pushed ref's own copy | **Rejected.** The ref that carries the sealed result would also carry the code that receives the credential. |
| **B2** — unprivileged `push` trigger (`permissions: {}`) plus a `workflow_run` job | trigger: pushed ref; privileged job: default branch | **Safe but optional.** Adds a second workflow class and ref-derived data for a latency gain only. The trigger's dependence on finding 1 (unproven for a Routine push) means it could not replace the sweep in any case. Specified as conditional follow-up F16. |
| **B′** — one privileged workflow, `schedule` + `workflow_dispatch` only, default-branch definition | `schedule`: default branch; `workflow_dispatch`: the selected ref, credentialed only on `main` | **Chosen.** No ref-triggered workflow exists at all; correctness never depends on an event firing. |

## 4. Exact permissions and rulesets

**Tokens** (two mints per pass, each `repositories: code-review-skill`):

| Token | Permission | Used for |
| --- | --- | --- |
| `GITHUB_TOKEN` (job) | `contents: read` | check out the default branch; fetch sealed refs |
| App token, phase 1 | `contents: write` | create record and receipt files on `benchmark-history`; bootstrap a lane's baseline pointer; delete a consumed `claude/benchmark-result-*` ref |
| App token, phase 2 | `issues: write` | evidence comments, drift and missed-run issues, close, health-status edit |
| — | never: `actions`, `workflows`, `administration`, `pull-requests`, `secrets`, `environments` | — |

The publisher has no label-creation capability (labels are a provisioning
prerequisite), even though `issues: write` would permit it.

**Environment.** A dedicated `benchmark-publication` environment holds the App
ID and private key; its deployment branch policy is the default branch only.
For contrast, the existing `release` environment (repo) has no protection rules
and no branch policy, and holds the release App's secrets — the benchmark
environment should be stricter.

**Rulesets** (provisioning, F7; nothing created here):

| Ref | Rules | Bypass | Note |
| --- | --- | --- | --- |
| `main` | unchanged: deletion, non-fast-forward, pull request, required status checks | live: **Admin role and the release App** (the release docs say the App only — a drift observed, not fixed here) | The benchmark App is never added; `GITHUB_TOKEN` cannot bypass. |
| tags | new: restrict creation, update, deletion | release App | `contents: write` would otherwise let the benchmark App create tags. Only one ruleset (`main`) exists today. |
| `benchmark-history` | restrict updates, restrict deletions, block force pushes | the benchmark App; per M7, the Admin role | The single-writer guarantee only an App (not `GITHUB_TOKEN`) can hold. |
| `claude/benchmark-result-*` | restrict deletions, block force pushes — **not** creation or update | the benchmark App; Admin | Creation and update must stay open because the provider's push authenticates as the maintainer. |

## 5. What makes B′ incapable of executing or judging the benchmark

1. **Triggers:** `schedule` and `workflow_dispatch` only. `schedule` runs the default-branch
   definition; a dispatch runs the selected ref's copy, and only a `main` run receives the App
   key (environment deployment policy).
   A policy test rejects any other trigger in the publication workflow.
2. **Credentials:** the environment holds only the App ID and key; no model,
   Claude, or provider credential exists in the repository or environment.
3. **Code:** the publication CLI's import graph excludes the benchmark
   entrypoint, the reviewer adapter, and `classify_drift`; a policy test
   enforces it. The publisher reads `drift.confirmed[]` and fingerprints from
   the sealed record and never recomputes them.
4. **Inputs:** sealed records and refs are fetched into a scratch directory and
   parsed as data; nothing from a ref, record, issue, PR, comment, or label is
   evaluated, sourced, or interpolated into a shell. Dispatch inputs are
   pattern-validated.
5. **No recursion:** the workflow listens to no event on `benchmark-history`
   or on staging refs, so App-token writes cannot re-trigger it (checked by the
   same policy test).

## 6. Watchdog, designed separately from publication

The watchdog must detect the **absence** of a result after `max_gap_hours`, so
it needs a timer; publication does not. It reads record metadata only
(`finished_at`, `trigger`), never executes the benchmark, and never judges
drift.

| Option | Verdict |
| --- | --- |
| **W1 — the `schedule` trigger of the publication workflow** | **Chosen.** No new host, secret, or token. |
| W2 — arrival events only | Cannot detect absence. |
| W3 — external timer that dispatches the workflow | Needs a timer host and a dispatch token; removes only W1's caveats. Not smaller. |
| W4 — a second Routine | An LLM session, capped by the daily run allowance, would hold a GitHub write path. |
| W5 — the next benchmark run reports the previous gap | Fails exactly when the Routine is dead. |

W1's caveats, stated rather than hidden: scheduled runs use the default branch,
can be delayed and, under heavy load, queued jobs may be dropped; the shortest
interval is five minutes, and in a public repository scheduled workflows are
**disabled after 60 days without repository activity**. The health status
therefore shows the last successful sweep, and the maintainer checks in
[`drift-issue-lifecycle-and-recovery.md`](drift-issue-lifecycle-and-recovery.md)
§7 include "publication workflow enabled". The repository merged 275 commits to `main` in the 31 days to 2026-09-19,
and W3 is the fallback if activity ever lapses.

## 7. Comparison and decision

| Operational item | A — external publisher | **B′ — publication-only Actions** |
| --- | --- | --- |
| Hosting | a maintainer-run host | none (GitHub-hosted runner) |
| Scheduling / polling | host timer polling refs | `schedule` polling; free on a public repository |
| Deployment / update | a separate deploy path, kept in sync with the record schema | merge to the default branch is the deploy |
| Secret store | host secret store | GitHub environment secrets, default-branch-only |
| Availability monitoring | monitor the host and its timer | Actions run status plus the health status |
| Disaster recovery | manual `--once` | `workflow_dispatch`, then manual `--once` |
| Concurrency | single-instance assumption or an added lease | native `concurrency` group |
| Provenance | host logs | run URL recorded in the receipt |

**Would A provide a guarantee B′ cannot?** Two candidates, neither required by
the boundary. (1) Independence from Actions-specific outages or a disabled
schedule: B′ mitigates with dispatch and local `--once`, and both designs
depend on the GitHub API. (2) Key custody outside GitHub: both hold the same
App key in a secret store gated to reviewed code; B′'s is gated to the default
branch. **Both architectures preserve the execution/publication boundary and
the security properties; B′ is the smaller operational architecture, so it
wins.** D1, D3, and D7 are unchanged; D2 and D4 are clarified in wording only; D5, D6, D8, and D9 change, as recorded in
[`decision-record.md`](decision-record.md) §3.

**Residual risks** (recorded, not resolved): finding 1's Routine-push trigger is
unproven (harmless to correctness); the activity API's permissions and
retention are undocumented (fail-closed, with a dispatch fallback); scheduled
workflows can lapse (visible in the health status); the provider-native GitHub
identity of the Routine remains outside this repository's control (R1).
