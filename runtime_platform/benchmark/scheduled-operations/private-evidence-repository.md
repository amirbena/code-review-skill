# ADR: Private Evidence Repository and Source/Evidence Separation

Architecture decision record for GitHub Issue
[#687](https://github.com/amirbena/code-review-skill/issues/687) (epic
[#686](https://github.com/amirbena/code-review-skill/issues/686); blocks
[#688](https://github.com/amirbena/code-review-skill/issues/688)). Like the rest
of [`./`](README.md), this is a **repository-development record, not packaged
into either Skill archive**.

**Status: accepted (architecture only).** Docs only. No code, Routine,
workflow, repository, ruleset, App installation or ref was created or changed
while producing it.

| Aspect | State |
| --- | --- |
| Architecture (Fully Private evidence, §2) | **Accepted.** The maintainer merged [PR #693](https://github.com/amirbena/code-review-skill/pull/693) (`6c82239`, 2026-10-10) and closed #687 as completed. The ADR named maintainer review as its gate. The maintainer confirmed on PR #700 that the merge and the closure are sufficient evidence of acceptance. |
| Implementation | **Destination contract delivered under `pre_cutover`** by [#688](https://github.com/amirbena/code-review-skill/issues/688) ([PR #698](https://github.com/amirbena/code-review-skill/pull/698), `71acb33`; §14). **Still pending:** the private-phase public-log field policy (§5.4, F12/F13), which that PR does not implement, and the cutover precondition G-open-1. Validation by [#689](https://github.com/amirbena/code-review-skill/issues/689) is recorded in the [validation gate](private-evidence-validation-gate.md). |
| Cutover | **Pending**, owned by [#690](https://github.com/amirbena/code-review-skill/issues/690). The manifest is still `pre_cutover` and no private repository exists. |

Clarified by [#699](https://github.com/amirbena/code-review-skill/issues/699):
the disposition of existing public automated issues (Q3, §10) and the public log
allowlist (§5.4). That clarification adds no decision to §2 and changes nothing
accepted.

Where this ADR changes an earlier decision, the earlier document carries a
pointer to this one. The earlier text stays in force until #688 implements the
change and #690 cuts over.

## 1. Context

Today, *where evidence lives* is an implicit property of `origin`, the public
source repository `amirbena/code-review-skill`:

- execution seals through `benchmark_seal.seal_to_ref` (a non-forced push,
  confined to `claude/`, then read back) to `--seal-remote`, which defaults to
  `origin` in
  [`run_benchmark_routine.py`](../scripts/run_benchmark_routine.py) and
  [`run_severity_observation.py`](../scripts/run_severity_observation.py);
- execution reads baselines through `benchmark_baseline.GitRefHistory`, whose
  remote also defaults to `origin`. The lane entrypoint passes `--seal-remote`
  to it, so reads and writes already share one remote name;
- the publisher addresses `repos/{manifest.repository}` for refs, contents,
  activity, commits, issues and permalinks. Its App tokens are minted with
  `repositories: code-review-skill`, and origin attestation requires a
  `branch_creation` by an actor in `publication.pusher_allowlist`;
- `provenance.repo` in every sealed record and observation is the source
  repository (`manifest.repository` / `spec.repository`).

Epic [#686](https://github.com/amirbena/code-review-skill/issues/686) moves
Routine-generated evidence to a private repository,
`amirbena/code-review-skill-evidence`. This ADR fixes what that move must
preserve and the smallest mechanism that enforces it.

### 1.1 Evidence observed on 2026-10-10

Each row can be re-checked with the command shown.

| # | Observation | Re-check |
| --- | --- | --- |
| O1 | `origin` currently holds **no** `claude/*` evidence refs. `benchmark-history` holds 7 sentinel records and receipts, plus `baselines/sentinel.json` (bootstrap, promoted by `benchmark-publication[bot]`). | `git ls-remote origin 'refs/heads/claude/*' refs/heads/benchmark-history` |
| O2 | On 2026-10-10 at 08:27Z, the maintainer deliberately reset historical execution evidence by deleting 7 `claude/benchmark-result-sentinel-*` refs and 5 `claude/severity-observation-*` refs. This was intentional and maintainer-authorized, not an incident or data loss, and the refs are not to be restored. | `gh api "repos/amirbena/code-review-skill/activity?activity_type=branch_deletion"` |
| O3 | Records published before the reset keep a `raw.location` that names their staging ref. After the reset, that location no longer resolves. This is expected: the record and receipt on `benchmark-history` remain the authoritative evidence. | the records on `benchmark-history`; O2 |
| O4 | `run_severity_observation.py` computes its stop condition (14 observations) and its one-per-day check from `ls-remote` of `claude/severity-observation-*` on the seal remote. Because of the O2 reset, the count starts again from zero. The maintainer accepts this. It also shows that a stop-condition count is a property of the store it reads, which is why §10 has a counted-refs rule. | [`run_severity_observation.py`](../scripts/run_severity_observation.py) `prior_observation_refs`, `skip_reason` |
| O5 | #681 is merged ([#692](https://github.com/amirbena/code-review-skill/pull/692), `d20d21d`). It adds `claude/concurrency-experiment-*` and `claude/concurrency-trial-*` and a spec `storage` block, and it follows the severity pattern: `run_concurrency_experiment.py` defaults `--seal-remote` to `origin` and counts prior experiment refs with `ls-remote` on that remote (`prior_experiment_refs`). Its Routine is not activated. | `git show d20d21d --stat`; `grep -n "seal-remote\|prior_experiment_refs" runtime_platform/benchmark/scripts/run_concurrency_experiment.py` |
| O6 | Live rulesets: `benchmark-history` (update, deletion and non-fast-forward, bypassed by the Admin role and the App) and `benchmark-staging-refs`, which covers **only** `refs/heads/claude/benchmark-result-*` (deletion and non-fast-forward). No ruleset covers `claude/severity-*` or `claude/benchmark-handoff-check-*`. | `gh api repos/amirbena/code-review-skill/rulesets/<id>` |
| O7 | `amirbena/code-review-skill-evidence` does not exist yet. The `benchmark-publication` environment exists with a custom deployment-branch policy. | `gh repo view amirbena/code-review-skill-evidence`; `gh api repos/amirbena/code-review-skill/environments` |
| O8 | Routine documentation (research preview): a routine selects "one or more GitHub repositories", each cloned at the start of a run from its default branch. Pushes go to `claude/`-prefixed branches by default. Rulesets apply to the connected GitHub access, and "a rule that access can bypass doesn't block a run's push". | [Routines](https://code.claude.com/docs/en/routines), "Repositories and branch permissions" |
| O9 | GitHub documents environment secrets and deployment-branch policies in **private** repositories as Pro/Team/Enterprise features. On Free they apply to public repositories only. Ruleset availability for private repositories on the maintainer's plan is unverified (the account's plan is not readable with the current token). | [Deployments and environments](https://docs.github.com/en/actions/reference/workflows-and-actions/deployments-and-environments) |

O2–O4 inform two rules in this ADR. First, a maintainer-authorized reset is a
legitimate retention action (§3.1). Second, a stop condition counts whatever
store it reads, so it restarts when that store's counted refs are reset or
replaced (§10).

## 2. Decision summary

| # | Decision |
| --- | --- |
| E1 | **Two stores, one owner per artifact** (§3). The public repository owns source; the private repository owns all execution evidence, `benchmark-history` (including the baseline pointers) and every automated benchmark issue. |
| E2 | **An explicit evidence destination in one of two declared phases** (§4). A repository-owned `evidence` block declares `phase`, `repository`, the namespace allow-list and no credential. In `pre_cutover` the evidence repository must equal the source. In `private` it must differ. Every run proves that its git remote is the declared repository. There is no implicit fallback to `origin`, or to any other repository, in either phase. |
| E3 | **The publisher stays the publication-only workflow in the public repository.** It uses the same `benchmark-publication` App, installed on the evidence repository, and every token is scoped to the evidence repository only. Actions is disabled in the evidence repository (§6, Q1). |
| E4 | **`baselines/<lane>.json` is evidence** and moves with `benchmark-history`. Expected baselines in fixtures stay public (§8, Q2). |
| E5 | **Automated tracking, health, drift and missed-run issues move to the evidence repository.** In the `private` phase the public repository receives no automated issue, comment or log content derived from evidence. Existing public automated issues have a stated disposition (§8, Q3), and public logs are limited to the allowlist (§5.4). |
| E6 | **One namespace registry, one ruleset over `claude/**`** in the evidence repository. In the `private` phase, the public repository gets a no-bypass ruleset that blocks creating evidence-namespace refs (§8, Q4). |
| E7 | **An explicit remote is sufficient.** No storage abstraction or new backend is added. Git refs stay the storage, and ref names stay unchanged (§8, Q5). |
| E8 | **Records do not depend on where they are stored.** No sealed field names the storage destination, so a migrated copy keeps its `content_sha256` and commit SHA. `provenance.repo` always names the source repository, never the storage destination, in both phases (§7). |
| E9 | **One active store at a time**, selected by `evidence.phase` and `evidence.repository` in the manifest at the SHA a run checks out. Cutover and rollback each change both values in one commit, through drained, paused transitions (§10). |
| E10 | **The concurrency campaign (#681–#683) is independent of this migration.** Neither blocks the other. Concurrency refs go to whichever store is active at the run's pinned SHA. A cutover must not disturb a campaign that is in progress (§10, §11). |

## 3. Ownership table

"Owner" is the repository that is authoritative for the artifact in the
`private` phase. In `pre_cutover` both columns are the source repository.
"Retention" is the rule the contract requires. A rule that differs from current
code is marked *new*.

### 3.1 Evidence (private: `amirbena/code-review-skill-evidence`)

| Namespace / artifact | Writer | Readers | Retention |
| --- | --- | --- | --- |
| `claude/benchmark-result-<run_id>` (staging seal: `benchmark-result.json`, `raw-bundle.json`) | Routine, through the seal (provider-mediated push) | publisher `sweep` (matching-refs and activity); `raw.location` resolution by a maintainer | Deleted by the publisher 30 days after its receipt (`DELETE_STAGING_REF`), and never before a receipt exists. Earlier deletion is allowed only as a maintainer-authorized reset (O2). After a reset, `raw.location` in already-published records stops resolving, and the record stays authoritative. |
| `claude/benchmark-handoff-check-<UTC>-<sha12>` (`handoff-check.json`) | Routine `auth-check` | maintainer only; never swept | The maintainer deletes it after reading the smoke-test result. No automatic deletion. |
| `claude/severity-observation-<run_id>` | Routine, `--trigger scheduled` | the entrypoint's stop condition and same-day guard (`ls-remote`); #653 analysis | Kept until #653 has read them (spec `removal_path`), unless the maintainer authorizes a reset. A reset restarts the stop-condition count from zero (O4). |
| `claude/severity-trial-<run_id>` | manual or API runs of the same entrypoint | none (never counted) | Maintainer discretion. |
| `claude/concurrency-experiment-<run_id>` (#681) | Routine, scheduled | the #681 stop condition (`ls-remote`); #682 analysis | Kept until #682 has read them (#683 removal path). The same reset rule as for severity refs applies. |
| `claude/concurrency-trial-<run_id>` (#681) | manual or API runs | none (never counted) | Maintainer discretion. |
| `benchmark-history` → `records/<lane>/<yyyy>/<run_id>.json` | publisher App, create-only | execution (baseline record), publisher, watchdog | Never pruned. |
| `benchmark-history` → `receipts/<lane>/<yyyy>/<run_id>.json` | publisher App, create-only | publisher (already-published check), watchdog | Never pruned. |
| `benchmark-history` → `baselines/<lane>.json` | publisher App (bootstrap); maintainer (promotion) | execution (`GitRefHistory`), publisher | One pointer per lane; replaced only by explicit maintainer promotion. |
| Lane tracking issues (today #486, #487), health issue (#488), `benchmark-regression` drift issues, `benchmark-missed-run` issues, evidence and status comments | publisher App (`issues: write`) | maintainer; publisher (markers) | Issues are never deleted; they close under the existing lifecycle rules. The public issues that exist today are not copied here; Q3 gives each one's disposition. |
| Labels `benchmark-regression`, `keep-open`, `benchmark-missed-run`, `benchmark-tracking` | maintainer (provisioning) | publisher | Provisioned in the evidence repository. The publisher still cannot create labels. |

### 3.2 Source (public: `amirbena/code-review-skill`)

| Artifact | Why it is source, not evidence |
| --- | --- |
| Entrypoints, publisher code, schemas, `benchmark-publish.yml` | code reviewed on `main` |
| `schedule/expected-run-manifest.json`, `schedule/*-spec.json` (including the new `evidence` block) | repository-owned configuration; identities only, no credentials |
| Fixtures and their **expected** findings (the "expected baselines"), corpus membership | the benchmark's definition, not an observation of a run |
| Development issues and PRs, docs, Wiki | development record. A maintainer may cite a private `run_id` in a development issue in their own words; nothing automated writes there (E5). #650 and the closed #569–#571 are of this kind after cutover (Q3) |
| `main`, tags, release refs, harness development branches (`claude/issue-<n>-<hash>`) | source and release history. These `claude/` refs are agent working branches, not evidence |

### 3.3 Inventory check

The validation command for the acceptance criterion is to find every
benchmark ref prefix that code can write or read:

```bash
grep -rnE "claude/[a-z]" runtime_platform/benchmark .github/workflows --include='*.py' --include='*.json' --include='*.yml'
```

On `main` at `d20d21d` (which includes #681) it yields six prefixes:
`claude/benchmark-result-`, `claude/benchmark-handoff-check-`,
`claude/severity-observation-`, `claude/severity-trial-`,
`claude/concurrency-experiment-` and `claude/concurrency-trial-`. It also
yields two concrete `claude/benchmark-result-sentinel-…` names, which come from
`schemas/examples/*.record.json` and are instances of
`claude/benchmark-result-`. The pattern skips the bare confinement prefix
`claude/` in `benchmark_seal.py`, and `tests/` is outside its scope. Every other
`claude/` string in the repository is a path (`.claude/skills/`,
`.claude/agents/`, `distribution/claude/`), not a ref. All six prefixes are in
§3.1. #688 turns this grep into a policy test against the namespace registry
(F10).

## 4. Destination configuration contract

### 4.1 Two explicit phases

The destination contract always runs in exactly one of two **phases**,
declared in configuration. Nothing infers a phase from which remotes exist,
from the remote name `origin`, or from whether the private repository is
reachable.

| Phase | `evidence.repository` | Where evidence reads and writes go | Purpose |
| --- | --- | --- | --- |
| `pre_cutover` | **must equal** the top-level `repository` (the source) | the source repository, reached through a remote whose identity is proven (§4.3) | Today's behavior, made explicit, so that #688 can land before #690 and existing Routines keep working unchanged |
| `private` | **must differ** from the top-level `repository` | the private repository only, reached through a remote whose identity is proven | The target state after #690 |

The phase is the only switch. Equality between source and evidence repository
is allowed **only** in `pre_cutover`, where it is required. In `private` it is
forbidden. No phase allows a fallback from one repository to another.

### 4.2 What the repository declares

The expected-run manifest gains one block, and each temporary spec
(severity, concurrency) refers to it rather than copying it. Before #690
(`pre_cutover`):

```json
"evidence": {
  "phase": "pre_cutover",
  "repository": "amirbena/code-review-skill",
  "namespaces": [
    "claude/benchmark-result-",
    "claude/benchmark-handoff-check-",
    "claude/severity-observation-",
    "claude/severity-trial-",
    "claude/concurrency-experiment-",
    "claude/concurrency-trial-"
  ],
  "history_branch": "benchmark-history"
}
```

After #690 the same block reads `"phase": "private"` and
`"repository": "amirbena/code-review-skill-evidence"`. The two values change in
one commit, and that commit **is** the cutover (§10).

- `phase` is required and is one of `pre_cutover` or `private`. A missing or
  unknown value is a configuration error in the manifest validator and in
  every entrypoint and publisher run (§4.4).
- `repository` is required. It is an **identity** (`owner/name`), never a URL,
  a token or a key. Its relation to the top-level `repository` is fixed by the
  phase (§4.1).
- The top-level `repository` (or a temporary spec's own top-level
  `repository`) always names the source, in both phases. It is the only input
  to `provenance.repo` (§7).
- `namespaces` is the **allow-list** (the namespace registry). A producer may
  write only refs that start with a registered prefix, in either phase. A new
  evidence namespace is added here in the same PR that introduces it (Q4).
- The exact key names are #688's choice. The semantics above are the contract.

### 4.3 How a run resolves the destination

The destination's **identity** always comes from `evidence.repository`. A run
only resolves the git remote that reaches that identity. Before any fixture
runs, every non-dry-run entrypoint must:

1. validate the `evidence` block (phase, repository and their relation, §4.1).
   On failure, exit 2. A dry run (`--seal-dir`) needs no destination;
2. pick the transport remote:
   - if the run supplies an evidence remote (a remote name or URL), use it;
   - otherwise, in `pre_cutover` only, use the checkout's own remote. This is
     **not** a fallback. That remote must pass the same identity proof in
     step 4 and is refused if it does not. This is what keeps existing Routine
     prompts, which pass no remote, operational;
   - otherwise, in `private`, exit 2 (missing destination). The private clone
     is a separate checkout (O8), so its remote must be supplied explicitly.
     How the prompt supplies it is experiment X1;
3. refuse a remote URL with embedded credentials (`user:token@`). The URL is
   never printed unredacted;
4. **prove identity**: the remote URL's path must end in `evidence.repository`
   (optionally followed by `.git`). A mismatch exits 2. A test-only override
   for a local bare repository is allowed, and it must be impossible to enable
   from a Routine prompt (for example, an environment variable that the test
   harness sets);
5. run a **preflight read** (`ls-remote` of `evidence.history_branch`). If
   that fails, exit 3 (`evidence-store-unavailable`) before any model cost is
   spent.

`GitRefHistory`, the severity and concurrency stop-condition reads, and the
seal all take the **same resolved destination**. A producer has no separate
remote argument that could diverge from the others.

### 4.4 Contract validation matrix

Each row is one test case for #688 (unit or policy test against a stubbed or
bare-repository remote). "Source" means the top-level `repository`.

| # | Phase | `evidence.repository` | Run-time situation | Outcome |
| --- | --- | --- | --- | --- |
| V1 | `pre_cutover` | = source | remote proven to be the source | **accepted**: reads and writes go to the source |
| V2 | `pre_cutover` | ≠ source | any | **rejected**, exit 2: in `pre_cutover` the repository must be the source |
| V3 | `private` | ≠ source | remote proven to be `evidence.repository` | **accepted**: reads and writes go to the private repository only |
| V4 | `private` | = source | any | **rejected**, exit 2: in `private` the repository may not be the source |
| V5 | either | missing | any | **rejected**, exit 2 (missing destination) |
| V6 | `private` | ≠ source | no evidence remote supplied | **rejected**, exit 2 (missing destination). The checkout's own remote is not used |
| V7 | missing or unknown value | any | any | **rejected**, exit 2 (missing or invalid phase) |
| V8 | either (valid) | valid for phase | supplied or resolved remote does not prove to be `evidence.repository` | **rejected**, exit 2 (identity mismatch). There is no retry against another remote |
| V9 | either (valid) | valid for phase | remote has embedded credentials | **rejected**, exit 2 |
| V10 | either (valid) | valid for phase | proven remote is unreachable or unauthorized | **explicit failure**, exit 3 (`evidence-store-unavailable`) before any fixture runs. Nothing is written to any repository |

The manifest validator enforces V2, V4, V5 and V7 statically, so a bad block
cannot merge. The entrypoints and the publisher enforce them again at run time.

### 4.5 What the publisher uses

The publisher's target repository is `evidence.repository`, in both phases,
after the same validation (§4.1, V2/V4/V5/V7). It never comes from
`GITHUB_REPOSITORY` or from the top-level `repository`. Permalinks, activity
queries, matching-refs, contents, issues and the health issue all use that
one value. In `pre_cutover` that value is the source, so today's publication
is unchanged.

## 5. Read/write contracts and failure semantics

### 5.1 Execution side

| Operation | Contract |
| --- | --- |
| Seal (write) | A plain push of one orphan commit to `<registered prefix><id>` on the resolved destination, then an `ls-remote` read-back. Never forced; an existing ref means a refusal. Unchanged from `benchmark_seal`, plus the namespace allow-list check. |
| Baseline / history (read) | Read-only `ls-remote`, `fetch` and `show` of `evidence.history_branch` on the resolved destination. An absent pointer gives `bootstrap`. An unreachable store **after a successful preflight** gives `incomparable`, as today. |
| Stop condition / duplicate run (read) | `ls-remote --heads` of the counted prefix on the resolved destination. A failure means **no run** (fail closed), never "zero refs". |

### 5.2 Exit statuses (execution entrypoints)

| Exit | Status | Meaning | Local diagnostics |
| --- | --- | --- | --- |
| 0 | `ok` / `skipped` | sealed, or an intentional skip (stop condition, same day) | JSON summary on stdout |
| 1 | `run-failed` | benchmark or verification failure, as today | stderr |
| 2 | `evidence-destination-misconfigured` | missing or invalid phase; missing destination; a repository that breaks its phase's rule (V2, V4); identity mismatch; credentials in the URL; a ref outside the allow-list (matrix §4.4) | stderr names the rule broken. The URL is redacted |
| 3 | `evidence-store-unavailable` | preflight, stop-condition read, or push failed (unreachable, unauthorized, rejected) | The would-be sealed files are written to a local diagnostics directory (`--seal-dir` semantics). stdout carries a JSON status with `run_id`, the destination identity and the git error class, and the run counts as **unsealed** |
| 3 | `seal-unconfirmed` | the push succeeded but the read-back failed or did not match | Same diagnostics as above. The ref may exist on the evidence destination only, and the publisher treats it like any other sealed ref (F4a) |

In either phase, a non-zero exit never falls back to another destination and
never claims publication. The Routine prompt keeps its rule: on a non-zero exit, stop, do
not retry, and push nothing else. Local diagnostics are best-effort, because a
Routine sandbox does not outlive its session. The session transcript holding
stdout is the durable trace, and an unsealed run is still not evidence.

### 5.3 Publication side

| Operation | Contract |
| --- | --- |
| Read handoff | matching-refs and activity on `evidence.repository` with an App token |
| Persist / receipt / baseline bootstrap | create-only contents writes to `benchmark-history` on `evidence.repository` |
| Issues and comments | `evidence.repository` only |
| Watchdog history read | an App token with `contents: read` on `evidence.repository`. The job's `GITHUB_TOKEN` cannot read a private repository, so the current `BENCHMARK_READ_TOKEN=github.token` mapping must change no later than the cutover commit |
| Failure | An invalid `evidence` block (V2, V4, V5, V7), a token mint failure, a 401/403/404 on `evidence.repository`, or an App-slug mismatch fails the job, with no write to any repository. There is no override that points the publisher at any repository other than `evidence.repository` |

**Log hygiene** (*new*, because the workflow's logs are public): in the `private`
phase, everything `benchmark-publish.yml` writes to a public surface (step
stdout and stderr, `::error::`/`::warning::` annotations, `GITHUB_STEP_SUMMARY`,
job outputs, uploaded artifacts) is limited to the allowlist in §5.4. The sweep and the watchdog must
satisfy it (F12, F13) no later than the cutover commit. #688 as merged does not
yet (§14).

### 5.4 Public log allowlist (private phase)

**What is emitted today** (on `main` at `71acb33`; re-check: `grep -nE "print\(" runtime_platform/benchmark/publisher/cli.py`;
the `Watchdog` and `Sweep` steps of the workflow):

| Surface | Content today | Public? |
| --- | --- | --- |
| `sweep` stdout | the full sweep report JSON (per run: `ref`, `run_id`, `status`, `detail`, `gate`, `commit`, `actions`, `deferred`) | No: the workflow redirects it to `$SWEEP_REPORT` in the runner temp directory. It is read only by the watchdog step |
| `sweep` stderr | one line per refused or failed run: `<status>: <ref>: [<gate>]` (#688 removed the `detail` text), plus `aborted: <reason>` | **Yes** |
| `watchdog` stdout | the report JSON: per lane `lane`, `action`, `overdue`, `missed_run_issue`, `expected_from`, `latest_run_id`, `finished_at`; and `health` with `action`, the open drift and missed-run issue counts, `pending_handoffs`, `last_successful_sweep` | **Yes** |
| `watchdog` stderr | `aborted: <reason>`, `acting identity: …` | **Yes** |
| `error: <message>` and uncaught tracebacks | arbitrary exception text. API errors are formatted as `<METHOD> <path>: <message>`, so a private API path and the GitHub response message can reach the log | **Yes** |

**Rule.** A value may appear on a public surface only if its class is allowed
below, **and** it is validated against that class's fixed form immediately
before it is written. A value that is not on the list, or that fails validation,
is dropped or replaced by a fixed placeholder, and the run still reports its
status through the allowed codes. Nothing is allowed because it is "probably
harmless". The exact mechanism (one writer, a schema, or a test double) is
the implementation's choice. The contract is that no code path writes to a public surface
without passing through the allowlist.

**Allowed.** Each class derives only from the committed manifest, from ref
names and ref metadata, or from codes the publisher itself defines. None
derives from a record's content or from an issue's state. **Everything else is
prohibited**, including every field named in the field policy below.

| Class | Allowed form | Why it is allowed |
| --- | --- | --- |
| Acting identity | the App slug | already printed; not secret |
| Lane identifier | a lane named in the manifest | public configuration, and never read from a record |
| Run identifier | the lane or temporary `run_id` form of §7 (fixed pattern) | it is in the ref name, and it is already allowed here |
| Ref name | a registered namespace prefix plus a valid `run_id` (§3.1) | derived from the two rows above |
| Repository identity | `owner/name` exactly as in the manifest | public configuration; never a URL |
| Status and gate codes | a member of a closed set defined in code (the outcome statuses, the gate identifiers, `aborted` reason codes) | the publisher defines them, so they carry no run content |
| Pipeline counts | non-negative integers counting refs, pending handoffs or run outcomes **by publisher status code**. Never a count of drift or missed-run issues | derived from refs and from the codes above |
| `expected_from` | a UTC instant taken from the manifest | public schedule configuration |
| Booleans | `ok`, `dry_run`, and `scope` as a code | publisher-defined |

**Not allowed, in any form.** Raw model output; review findings and their
text; evidence excerpts or record fields; case results or drift observations;
private repository, issue, record or commit **URLs**, including API URLs; Routine provider session URLs; credentials, tokens and
authentication detail; arbitrary exception messages and tracebacks; refusal or
error `detail` text; and any other unbounded free text. In the `private` phase,
`detail` and an exception message are not written to a public surface at all. A
failure reports only its status and gate code (and its `run_id`), and the full
diagnosis is read from the private evidence repository or from the maintainer's
local run (§5.2). Whether the detail is persisted privately is the implementation's choice;
the contract only forbids a public write.

**Public surfaces beyond stdout and stderr.** `$SWEEP_REPORT` stays on the
runner, is passed only to the watchdog step, and is never printed, appended to
`GITHUB_STEP_SUMMARY`, or uploaded as an artifact. The workflow adds no step
summary, annotation or artifact that carries content outside the allowlist. A
`::error::` annotation follows the same rule.

**Failure behavior.** The log boundary is fail-closed in one direction: an
unvalidated or unknown value is withheld, never printed "as is". It must not
turn a publication failure into a success, so a withheld value never changes an
exit status. An uncaught exception must reach the public log only as a fixed
code, not as its message.

**Field policy (decided on PR #700).** The stricter fail-closed policy applies.
Each field below is emitted today. Each is derived from a record's content, from
schedule state or from an issue's state, so each stays **private** and must not
appear on any public surface in the `private` phase, whatever its value. There
is no "safe value" exception.

| Field (today's name) | Public in `private` phase? | Where it may be read instead |
| --- | --- | --- |
| `finished_at` | **No** | the private record, and the private health issue |
| `overdue`, and the watchdog's per-lane and `health` `action` | **No** | the private health and missed-run issues |
| `last_successful_sweep` | **No** | the private health issue |
| `missed_run_issue`, and every other issue number (private or public), however obtained | **No** | the private evidence repository |
| `open_drift_issues`, `open_missed_run_issues` and any other count of drift or missed-run items | **No** | the private health issue |
| `commit` (the persisted evidence commit SHA) and every other git object id from the evidence repository | **No** | the private repository |
| `detail`, `aborted` reason text, `error:` text, tracebacks | **No** (§5.4 "Not allowed") | local diagnostics, or the private repository |
| `identity`, `ok`, `scope`, `dry_run`, lane and run identifiers, `ref`, status and gate codes, pipeline counts, `expected_from` | Yes, as defined in "Allowed" | n/a |

A field that is not in either list is prohibited. This is **testable** as a
closed set: a test collects every key and every line that the sweep and the
watchdog write to stdout, stderr, annotations and the step summary, and asserts
that each belongs to the "Allowed" classes and none to the table above.

**What public CI communicates.** The workflow's own conclusion (success or
failure, from the exit code) is the primary signal. On top of that, each run may
print only fixed-form lines made of allowed values, for example
`sweep: ok=<bool> scope=<code>`, `<status-code>: <ref>: [<gate-code>]` for a
refused or failed run, `watchdog: ok=<bool>`, and `aborted: <reason-code>`.
Whether a lane is overdue, or a drift exists, is never printed. A maintainer
learns that from the private health issue. A failed watchdog or sweep step
fails the job, so operators see that something needs attention without seeing
what.

**Consistency.** The allowlist and its test (F12, F13) are not delivered by #688 as
merged, and the owner of that work is a maintainer decision. #689 checks it
against a run that uses fixture records and issue bodies carrying sentinel
strings. Neither may widen it. A widening is an edit to this section, in a PR
that links its own issue.

## 6. Authentication boundaries

| Identity | Scope in the `private` phase | Least-privilege rule | Verified? |
| --- | --- | --- | --- |
| **Routine** (provider-mediated, acting as the maintainer's connected GitHub access) | reads the source (clone); writes registered `claude/*` refs in the evidence repository; reads `benchmark-history` there | The Routine selects both repositories. No GitHub credential is provisioned into the runtime. The entrypoint writes only allow-listed refs to the proven destination. | **No.** Experiment X1. The docs say multiple repositories are supported. Whether the evidence clone's remote URL is usable from the source checkout, and whether access to a private repository requires the Claude GitHub App installed on it or a `/web-setup` grant, must be observed, not assumed. |
| **`benchmark-publication` App** | installed on the evidence repository. Tokens: `contents: write` (persist, delete staging), `issues: write`, `contents: read` (watchdog), each with `repositories: code-review-skill-evidence` only | never `actions`, `workflows`, `administration`, `pull-requests`, `secrets`, `environments` (unchanged). In the `private` phase the public repository is removed from the installation. | Installation and minting are checked by #689. Activity-API access on a private repository is experiment X3. |
| **Publication job `GITHUB_TOKEN`** | `contents: read` on the **public** repository (checkout only) | never used against the evidence repository | — |
| **Maintainer** | admin on both | promotion, approved deletions, provisioning, cutover | — |

**Residual R1, extended.** The Routine pushes as the maintainer, and an access
that can bypass a ruleset is not blocked by it (O8). On the evidence
repository, the Admin role's bypass therefore means a Routine push is
constrained by repository code and the allow-list, not by rulesets. On the
**public** repository, the no-bypass creation ruleset of Q4 is what makes
accidental public publication structurally impossible, because a ruleset with
an empty bypass list binds admins too.

**Why the key stays in the public repository (Q1).** The evidence repository
receives pushes from an LLM-driven session. If Actions were enabled there, any
pushed ref could carry a workflow file, and without a deployment-branch policy
an App key stored there would be readable by that workflow. Deployment-branch
policies and environment secrets for private repositories need a paid plan
(O9). Keeping the key in the public repository's `main`-only environment
preserves the existing guarantee on every plan.

## 7. Provenance requirements

Every sealed artifact (lane record, observation, experiment) carries, as
today:

- `run_id` (the lane form `<lane>-<YYYYMMDDTHHMMSSZ>-<sha12>`, or the
  temporary form `<UTC>-<sha12>`);
- source identity: `provenance.repo` = **the source repository** (the
  manifest's or spec's top-level `repository`), `provenance.repo_sha`,
  `provenance.ref`, `provenance.entrypoint_version`;
- manifest or spec identity: `provenance.spec_sha256` for lanes. Observations
  and experiments record their spec identity in the same way;
- `runtime.model_id`, `runtime.runtime_name`, `runtime.runtime_version`,
  `runtime.adapter_id`;
- `started_at`, `finished_at`, `sealed_at` (UTC).

Rules:

- **`provenance.repo` identifies the source, never the storage
  destination**, in both phases. It is computed only from the top-level
  `repository`, never from `evidence.repository` or from a remote. In
  `pre_cutover` the two values happen to be equal. That is a property of the
  phase, not a dependency, and nothing may read `provenance.repo` to find
  where evidence is stored.
- **No sealed artifact gains a storage-location field** (E8). The lane record
  schema (`benchmark-result/v1`) has `additionalProperties: false` on
  `provenance` and on `raw`, and its only location-like value is `raw.location`.
  That value is repository-relative (`<ref>:<file>`), so it resolves against
  whichever store holds the record. Adding a destination field would need a
  new schema version, and this ADR adds none. Observations and experiments
  follow the same rule. The storage destination is derivable from the
  manifest at `provenance.repo_sha`.
- The **receipt** may name the store (`record_permalink` is a URL into it).
  Receipts written in `pre_cutover` keep their public URLs; they are immutable
  history, not rewritten.

## 8. Decisions on the open questions

### Q1 — Where the publisher runs, and which App and installation it uses

**Decision:** keep `benchmark-publish.yml` in the public repository, with the
same triggers (`schedule` and `workflow_dispatch`), the same `main`-only
`benchmark-publication` environment and the same App. Install the App on the
evidence repository. Tokens are always minted for `evidence.repository`
(F11): the source in `pre_cutover`, and `repositories: code-review-skill-evidence`
in `private`. Disable Actions in the evidence repository.

**Rejected:**

- *Move the workflow into the evidence repository.* Its logs would be private,
  but the key would sit in a repository that LLM-session pushes reach, and on a
  Free plan there would be no deployment-branch policy to contain it (O9, §6).
  It would also move the workflow definition out of reach of the public policy
  tests.
- *A second App for the evidence repository.* Two installations with the same
  blast radius add rotation work and give no isolation, since the public
  repository receives no writes in the `private` phase.
- *An external host.* The reasons for rejecting it in
  [`publication-architecture.md`](publication-architecture.md) §7 are
  unchanged.

**Condition that would reopen Q1:** if a plan with private-repository
environments is confirmed (X2) and public log exposure (F12) proves hard to
bound.

### Q2 — Classification of `baselines/<lane>.json`

**Decision: evidence**, so it moves with `benchmark-history`. It is a pointer
to a private record (`record_path`, `record_sha256`, `run_id`, `corpus_id`,
`promoted_by`), and without the record it is meaningless. Keeping it public
would publish run identity and timing of private evidence and would split one
history branch across two stores. The **expected** baselines (fixture expected
findings, corpus membership) are source and stay public, so anyone can still
see *what* is measured. Only *observed outcomes* become private. Promotion
remains an explicit maintainer action, now in the evidence repository.

### Q3 — What tracking, health and drift issues may expose publicly

**Decision: nothing, automatically.** All automated benchmark issues and
comments move to the evidence repository. This ADR separates two things:

- **Public development discussion** (allowed). An issue or comment that a
  maintainer or contributor writes about the benchmark, in their own words.
  It may cite a `run_id` and describe a regression.
- **Automated publication of operational evidence** (prohibited in the
  `private` phase). Any issue, comment, label, edit or log line that the
  publication workflow, the App or any other automation writes from benchmark
  records, drift, schedule state or health.

The prohibition follows the writer and the source, not the topic. In the
`private` phase the publisher addresses only `evidence.repository` (§4.5, F6),
so it cannot update a public issue even by mistake. No public status
projection or sanitized public summary is introduced. The rejection below
stands.

**Disposition of the public issues that exist today.** Checked against the
repository on 2026-10-10. A pointer comment states only that the topic "moved to
the private evidence store". It names no run, lane, drift case or count and has
no link into the private repository. The maintainer posts it (#690 owns the
action). Nothing here is deleted or edited, and no automated comment is copied
to the private repository.

| Public issue | State on 2026-10-10 | Disposition |
| --- | --- | --- |
| #486 sentinel tracking | open | Content-free pointer, then close, **after the cutover has succeeded** (§10 step 8) |
| #487 comprehensive tracking | open | Same |
| #488 health status | open | Same |
| #621 missed run, comprehensive lane | open (automated, `benchmark-missed-run`) | Content-free pointer, then close, **after the private watchdog has run successfully against the private store**. If the lane is still overdue, the private watchdog opens its own issue there |
| #650 drift, with a maintainer analysis | open (automated body, `keep-open`, maintainer comment) | **Preserved** as an existing manually maintained development issue. The maintainer's decision: it is **not** edited, closed, sanitized or migrated, and its historical content stays as it is. After cutover the private publisher must not update it (see the rule below) |
| #569, #570, #571 historical drift | closed (`not planned`, `completed`, `duplicate`) | **Preserved** as closed history. No migration, no reopening |

Rules that apply to every row:

- Historical content stays where it is, including the automated links in those
  issues to records on the public `benchmark-history` branch. Removing it, or
  moving it, is not part of this decision and would need its own maintainer
  decision.
- **After cutover the private publisher must not update #650, or any other
  public evidence-derived issue.** That means no edit, comment, label change,
  close or reopen. In the `private` phase it has no route to the public
  repository (§4.5, F6), and the App is removed from that installation (§6).
  New automated drift reporting belongs exclusively in the private evidence
  repository, where it opens its own issues. It does not adopt a public one.
- Public development issues remain allowed. A maintainer may open, write on or
  close them by hand at any time.
- Until cutover (`pre_cutover`), the publisher keeps managing these issues as it
  does today.

Public Actions logs are bounded by the allowlist (§5.4).

**Rejected:** *public issues with redacted summaries.* Every redaction rule is
another contract to keep correct, and drift fingerprints and case IDs already
reveal which fixtures regress.

### Q4 — Ruleset and retention coverage for present and future namespaces

**Decision:**

- Evidence repository rulesets: (a) `benchmark-history`: update, deletion and
  non-fast-forward, bypassed by the App and the Admin role (as today); (b)
  **one ruleset over `refs/heads/claude/**`**: deletion and non-fast-forward,
  bypassed by the App (staging deletion) and the Admin role (approved
  deletions). This closes the gap in O6, where only
  `claude/benchmark-result-*` was protected; (c) the default branch protected.
- Public repository, applied when the phase becomes `private`: one ruleset
  that **restricts creation** of
  every registered evidence prefix, with **no bypass actors**, so even an
  admin-identity Routine push to the source fails (§6).
- Retention per namespace is §3.1. A future namespace becomes writable only by
  being added to `evidence.namespaces` together with a retention row here (or
  in its own spec's `removal_path`). It is then covered by rule (b) and by the
  public creation block without any new ruleset.
- If X2 shows rulesets are unavailable for the private repository on the
  maintainer's plan, rule (a)'s single-writer guarantee and rule (b) do not
  exist there. That is a **blocking maintainer decision** for #689 (upgrade,
  or accept a weaker guarantee recorded in an issue), not something the
  implementation decides.

### Q5 — Is an explicit evidence remote sufficient?

**Decision: yes.** Every producer and consumer already speaks git refs
(execution) or the GitHub REST API for one repository (publisher). The defect
is that the destination is implicit, not that the storage model is wrong.
One declared phase and identity, one run-time remote that is proven against it,
and one publisher repository variable remove the defect. A storage abstraction
would add an interface with a single implementation, and an external store is
still the escape hatch defined in
[`canonical-result-and-persistence.md`](canonical-result-and-persistence.md)
§4.

## 9. Testable invariants

Each statement is phrased to be checkable by a unit or policy test against a
stubbed or bare-repository remote (#688), or by an observed check (#689).

**Failure**

- F1. In `private`, a non-dry-run entrypoint invoked without an evidence
  remote exits 2 and pushes nothing (V6). In `pre_cutover` the same invocation
  resolves the checkout's own remote, which must pass the identity proof (V1,
  V8).
- F2. Every rejected row of the matrix (§4.4: V2, V4–V9) exits 2 before any
  fixture runs and writes nothing to any repository.
- F3. An unreachable or unauthorized evidence remote (V10) exits 3 before
  any fixture runs (preflight), and no ref is created on any remote.
- F4. A rejected or failed push exits 3, writes the would-be sealed files to
  the diagnostics directory, and leaves no ref on any remote, `origin`
  included.
- F4a. If the push succeeds but the read-back fails, the run exits 3 with
  status `seal-unconfirmed`. The ref may exist on the evidence destination,
  and only there. If it does, the publisher treats it like any other sealed
  ref: it validates the ref and publishes it if valid. The executor never
  claims publication.
- F5. A stop-condition read failure exits 3 and runs nothing; it is never
  treated as "zero prior refs".
- F6. The publisher never sends a request to any repository other than
  `evidence.repository` (asserted on the fake GitHub client), and a 401/403/404
  there fails the job without writes.
- F7. Every scheduled-entrypoint stop condition counts refs on the resolved
  evidence destination only.

**Idempotency**

- I1. Sealing an existing ref is a refusal (non-forced push), and the run is
  unsealed.
- I2. Publishing a `run_id` already published with the same `content_sha256`
  is a no-op; with a different hash it is a conflict.
- I3. A sealed body's `content_sha256` is identical whether it is sealed to a
  bare "public" or a bare "private" test remote (E8).
- I4. Copying an evidence ref between stores preserves its commit SHA, and
  the copy validates with the same `content_sha256`.

**Provenance**

- P1. In both phases, `provenance.repo` equals the top-level `repository`
  (the source). Changing `evidence.repository` and `evidence.phase` while
  holding the top-level `repository` fixed does not change `provenance.repo`.
- P2. No sealed artifact has a field whose value is derived from
  `evidence.repository` or from the resolved remote (schema check, plus a
  test that seals the same inputs under both phases).
- P3. `run_id`, `repo_sha`, `model_id`, `runtime_version`, `spec_sha256` and
  the timestamps are present and unchanged in meaning (existing schema
  validation).

**Namespaces and scope**

- F8. A write to a ref outside `evidence.namespaces` is refused (exit 2).
- F9. The manifest validator accepts only the phase rules of §4.1. It rejects
  V2 (`pre_cutover` with a different repository), V4 (`private` with the
  source), V5 (missing repository) and V7 (missing or unknown phase).
- F9a. In `pre_cutover` (V1), a run whose prompt passes no evidence remote
  seals to the source repository and exits 0. #688 merging before #690
  therefore breaks no existing Routine.
- F10. Every `claude/<prefix>` constant in benchmark code is a registered
  namespace (the §3.3 grep as a policy test).
- F11. The publication workflow mints tokens only for
  `evidence.repository` (the source in `pre_cutover`,
  `code-review-skill-evidence` in `private`), and never grants
  the permissions listed as "never" in §6.
- F12. In the `private` phase, every public surface of the publication
  workflow (§5.4) carries only allowlisted values. A test feeds fixture records,
  issue bodies and exception messages that contain sentinel strings and asserts
  that none appears, and that none of the private fields of the §5.4 field policy
  appears for any input (`finished_at`, `overdue`, watchdog `action`,
  `last_successful_sweep`, issue numbers, drift and missed-run counts, evidence
  commit SHAs). The test fails if the sweep or the watchdog emits a key or line
  outside the allowed classes.
- F13. In the `private` phase, a failure reports a status code and a gate code
  without `detail` text, an uncaught exception reaches the public log only as a
  fixed code, and the job's success or failure is carried by its exit status.
  Withholding a value never changes that status.

**Rollback / migration**

- R1. At any commit of `main`, exactly one phase and one store are active:
  the manifest's `evidence.phase` and `evidence.repository`.
- R2. No run crosses a cutover. A run's destination is a pure function of the
  manifest at its `repo_sha`.
- R3. The publisher sweeps exactly one store per pass.
- R4. A migration step never deletes an evidence ref from any store until
  its copy in the active store is verified (same SHA) and the deletion is
  approved. A maintainer-authorized reset (O2) is a separate retention action:
  it deletes without copying, by design.

## 10. Migration and rollback invariants (for #690)

**Cutover order:**

0. **Gate.** The [validation gate](private-evidence-validation-gate.md) (#689) passes on the commit being
   cut over from, and its open precondition G-open-1 (the §5.4 public-log allowlist, F12/F13) is closed. The
   cutover commit of step 4 is not merged before this.
1. Pause the lane Routines and any other evidence-producing Routine. A
   temporary campaign's Routine stays enabled and is handled by the
   counted-refs rule below.
2. Drain the old store, so that every staging ref there has a receipt.
3. Copy whatever evidence refs exist at that moment, and `benchmark-history`,
   by SHA (I4). Verify each copy.
4. Merge the cutover commit, which changes `evidence.phase` from
   `pre_cutover` to `private` and `evidence.repository` to the private
   repository together (§4.2). The workflow's token scope changes in the same
   commit (F11). Then apply the public creation ruleset (Q4).
5. Update every evidence-producing Routine's prompt to supply the private
   evidence remote (V6), including a running campaign's Routine, before that
   campaign's next scheduled run. Then run one `auth-check` against the new
   store. A Routine that runs before its prompt is updated fails with exit 2
   (V6) and writes nothing. It never writes to the source repository.
6. Re-enable the paused Routines.
7. Delete refs from the old store only with recorded approval (R4).
8. Dispose of the public automated issues as Q3 lists, each one only after its
   condition holds: #486–#488 after the cutover verification of steps 4–5, and
   #621 after the private watchdog has run successfully. Leave #650 and
   #569–#571 as they are. The maintainer posts the content-free pointers.

Step 3 copies whatever exists at cutover. Refs removed by a maintainer-authorized
reset (O2) are not inputs and are not restored. Copied staging refs that already
have receipts are recognized as published. Copied refs without receipts would
be attested by the migrating maintainer, who is in the allowlist, which is why
step 2 comes first.

**Counted refs.** A stop condition counts the store that is active at the run's
pinned SHA. A cutover must not change a running campaign's count. If a
campaign is in progress, the cutover happens between two of its scheduled runs
and its counted refs are copied in step 3, so the next run sees the same count
in the new store. If the old store's counted refs were reset first by a
maintainer-authorized reset, the count restarts from zero, as in O4. Only such
a reset may restart a count.

**Rollback** has two forms:

- **R-a, pause (preferred):** disable the affected Routines and fix forward. Nothing is
  published and no store changes.
- **R-b, return to `pre_cutover`:** paused as in R-a, first disable the
  public creation ruleset (Q4), because its empty bypass list blocks the
  copy. Then copy post-cutover evidence back by SHA, and revert the cutover
  commit, which restores `phase: pre_cutover` and the source repository
  together. A prompt that still supplies the private remote then fails the
  identity proof (V8) instead of writing to the wrong store. R-b republishes
  private evidence in the public repository, so it needs explicit maintainer
  approval recorded in an issue.

In both forms, two stores never accept writes at the same time: a run's
destination comes from its pinned manifest (R2). The lane Routines are paused
across each transition, and a running campaign is switched between two of its
runs (§10).

## 11. Coordination with #680 (#681–#683)

- **The campaign is independent of this migration (E10).** The issue asked
  whether `claude/concurrency-*` should target the private repository from its
  first run. The maintainer decided it should not be tied to the migration.
  #681–#683 proceed on their own schedule, and no dependency on #688–#690 is
  proposed. Concurrency refs go to whichever store is active at the run's
  pinned SHA: the source repository in `pre_cutover` and the private one in
  `private`.
- **What the migration owes the campaign.** The two concurrency prefixes are in
  `evidence.namespaces` (§4.2), so #688's allow-list does not break the
  campaign. #689 validates them like any other namespace. #690 applies the
  counted-refs rule (§10), so a cutover during the campaign keeps its count.
  Refs produced in `pre_cutover` are migrated or deleted under the same rules as
  every other namespace.
- **#688 owns the integration.** #681 is merged (O5), so the shared
  destination contract is applied to its evidence paths by #688, not by #681.
  #688 must route all three through the contract of §4.3: the `--seal-remote`
  default, `prior_experiment_refs` (the stop-condition read, which fails closed
  per F5) and the seal call in `run_concurrency_experiment.py`. #688 also
  covers the concurrency refs in its stubbed-remote tests (F7, F8) and in the
  F10 namespace policy test. Until #688 lands, the entrypoint keeps today's
  behavior, which is exactly what `pre_cutover` (V1) describes, so no compat
  work is needed in #681's code.
- **No new dependency.** The campaign (#681–#683) does not wait for #688.
  Activating the Routine, running experiments and analysis all proceed under
  `pre_cutover` rules. If #688 lands during the campaign, the entrypoint's
  `pre_cutover` path (no remote supplied, checkout's own remote proven to be
  the source) keeps the campaign running unchanged. Only the `private` phase
  requires the Routine prompt to supply an evidence remote, and that is
  #690's step 5 (§10).
- **Sequencing:** #687 (this ADR) → #688 → #689 → #690. The campaign
  (#681 → #682 → #683) runs in parallel, and #690 schedules its cutover around
  the campaign's run dates.

## 12. Maintainer experiments (cannot be verified from the repository)

| # | Experiment | Decides |
| --- | --- | --- |
| X1 | A Routine selecting both repositories runs `git remote -v` in each clone and pushes one `claude/x1-*` ref to the private clone's remote from the source checkout. Then try a push to a non-`claude/` branch of the private repository. | the §4.3 supply mechanism for the `private` phase; whether private access needs the Claude GitHub App on that repository; R1's real scope |
| X2 | In the evidence repository's settings: whether rulesets and environments (with deployment-branch policies) are available on the account's plan. | the Q4 blocking decision; whether Q1 stays closed |
| X3 | Query `GET /repos/{evidence}/activity` with an App installation token after a Routine push. | whether origin attestation works unchanged in a private repository (fail-closed with dispatch fallback either way) |
| X4 | Check whether the provider's clone of the evidence repository fetches every branch. | whether clone time grows with evidence refs. If it does, keep the default branch minimal and document a size trigger |

## 13. Relationship to existing contracts

This ADR is consistent with, and narrows, the following:

- [`execution-publication-boundary.md`](execution-publication-boundary.md):
  the one-way boundary, H-A handoff, closed capability set and App permission
  set are unchanged. Only the repository they address changes. The §8
  reachability rows stay valid for the public repository, and §6 here adds
  the evidence-repository rows.
- [`canonical-result-and-persistence.md`](canonical-result-and-persistence.md):
  the record fields, run identity, layout and retention are unchanged. §3's
  "lives only on an orphan history branch" now means on the evidence
  repository. §5's "through the same repository access the checkout uses"
  becomes "through the resolved evidence destination".
- [`publication-architecture.md`](publication-architecture.md): B′ is kept.
  The §4 token rows change `repositories: code-review-skill` to the evidence
  repository. The watchdog's read token becomes an App token. The W1 caveat
  about 60-day disablement still applies to the public repository that hosts
  the workflow.

No contradiction was found that requires changing those documents' decisions.
Each carries a pointer to this ADR for the parts that change at cutover.

## 14. Implementation of the destination contract (#688)

Implemented under `pre_cutover`: the manifest block of §4.2 is committed with
`phase: pre_cutover` and `repository` equal to the source, so every existing
Routine prompt keeps working (F9a). Nothing here creates the private repository,
activates a Routine or migrates data (#690).

| Concern | Where it lives |
| --- | --- |
| Block validation (V2, V4, V5, V7), namespaces, `history_branch` | `scripts/benchmark_evidence_config.py`, enforced statically by `benchmark_schedule_manifest.py` and again at run time |
| Resolution, identity proof (V1, V3, V6, V8, V9), preflight (V10), allow-listed seal, stop-condition reads, baseline history | `scripts/benchmark_evidence_destination.py` (`Destination`); `GitRefHistory` has no remote default |
| Entrypoints | `run_benchmark_routine.py`, `run_severity_observation.py`, `run_concurrency_experiment.py`: one `--evidence-remote` (alias `--seal-remote`); exit 2 `evidence-destination-misconfigured`, exit 3 `evidence-store-unavailable` / `seal-unconfirmed` with the would-be files kept in a local `benchmark-unsealed-<run_id>` directory and a JSON status on stdout |
| Publisher | `publisher/cli.py` addresses `manifest["evidence"]["repository"]` only; `resolve-evidence` feeds token minting; refusal detail is not logged |
| Workflow | `benchmark-publish.yml` mints three single-permission App tokens (`contents: write`, `issues: write`, `contents: read`) for the resolved evidence repository only, pinned by `test_benchmark_publish_workflow.py` |

Identity is proven from the remote's URL path (a remote name is resolved with
`git remote get-url`); a URL with embedded credentials is refused and never
printed. A local path or `file://` remote is accepted only when the test harness
sets `BENCHMARK_EVIDENCE_TEST_LOCAL_REMOTES=1`, which a Routine prompt cannot do.
In `pre_cutover`, an omitted remote resolves the checkout's own `origin`, and only
after the same proof; in `private` it is refused (V6).

### 14.1 How the provider-side Routine authenticates to the private repository

Unchanged in principle from §6, and still to be observed (X1) rather than
assumed: the Routine **selects both repositories** in the provider's own product
surface, and the provider mediates every clone and push through the maintainer's
connected GitHub access. Nothing in this repository stores, prints or passes a
GitHub credential: the prompt carries only a remote name or a credential-free URL,
the entrypoints never read a token variable, and a URL with `user:token@` is
rejected (V9). Least privilege is therefore bounded by (a) the provider's grant
being limited to the two repositories, (b) the allow-list that restricts every
write to registered `claude/` prefixes, and (c) the public repository's no-bypass
creation ruleset of Q4 once the phase is `private`. If X1 shows the provider's
access to a private repository needs the Claude GitHub App installed there, that
installation is granted to the evidence repository only and carries no workflow
or administration permission.
