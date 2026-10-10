# ADR: Private Evidence Repository and Source/Evidence Separation

Architecture decision record for GitHub Issue
[#687](https://github.com/amirbena/code-review-skill/issues/687) (epic
[#686](https://github.com/amirbena/code-review-skill/issues/686); blocks
[#688](https://github.com/amirbena/code-review-skill/issues/688)). Like the rest
of [`./`](README.md), this is a **repository-development record, not packaged
into either Skill archive**.

**Status: proposed — awaiting maintainer review.** Docs only. No code, Routine,
workflow, repository, ruleset, App installation or ref was created or changed
while producing it. Where this ADR changes an earlier decision, the earlier
document carries a pointer to this one. The earlier text stays in force until
[#688](https://github.com/amirbena/code-review-skill/issues/688) implements the
change and [#690](https://github.com/amirbena/code-review-skill/issues/690)
cuts over.

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
| O2 | The maintainer deleted 7 `claude/benchmark-result-sentinel-*` and 5 `claude/severity-observation-*` refs at 2026-10-10T08:27Z, between 15 and 1 days after their receipts, so **before** the 30-day `DELETE_STAGING_REF` retention. The deletions used the Admin role's ruleset bypass. | `gh api "repos/amirbena/code-review-skill/activity?activity_type=branch_deletion"` |
| O3 | The 12 deleted commits still exist as remote-tracking refs in the maintainer's primary clone, and each still has its two files. This is the only known copy of the raw bundles that published records point to through `raw.location`. | `git for-each-ref 'refs/remotes/origin/claude/*'` in the primary clone |
| O4 | `run_severity_observation.py` computes its stop condition (14 observations) and its one-per-day check from `ls-remote` of `claude/severity-observation-*` on the seal remote. After O2, the next scheduled run counts **0**, so the campaign would collect up to 14 *more* observations, and the same-day guard has lost its input. | [`run_severity_observation.py`](../scripts/run_severity_observation.py) `prior_observation_refs`, `skip_reason` |
| O5 | #681 is in progress on `origin/feat/concurrency-measurement-routine` (not merged). It adds `claude/concurrency-experiment-*` and `claude/concurrency-trial-*`, with the same `ls-remote` stop-condition pattern and a spec `storage` block. | `git diff origin/main...origin/feat/concurrency-measurement-routine --stat` |
| O6 | Live rulesets: `benchmark-history` (update, deletion and non-fast-forward, bypassed by the Admin role and the App) and `benchmark-staging-refs`, which covers **only** `refs/heads/claude/benchmark-result-*` (deletion and non-fast-forward). No ruleset covers `claude/severity-*` or `claude/benchmark-handoff-check-*`. | `gh api repos/amirbena/code-review-skill/rulesets/<id>` |
| O7 | `amirbena/code-review-skill-evidence` does not exist yet. The `benchmark-publication` environment exists with a custom deployment-branch policy. | `gh repo view amirbena/code-review-skill-evidence`; `gh api repos/amirbena/code-review-skill/environments` |
| O8 | Routine documentation (research preview): a routine selects "one or more GitHub repositories", each cloned at the start of a run from its default branch. Pushes go to `claude/`-prefixed branches by default. Rulesets apply to the connected GitHub access, and "a rule that access can bypass doesn't block a run's push". | [Routines](https://code.claude.com/docs/en/routines), "Repositories and branch permissions" |
| O9 | GitHub documents environment secrets and deployment-branch policies in **private** repositories as Pro/Team/Enterprise features. On Free they apply to public repositories only. Ruleset availability for private repositories on the maintainer's plan is unverified (the account's plan is not readable with the current token). | [Deployments and environments](https://docs.github.com/en/actions/reference/workflows-and-actions/deployments-and-environments) |

O2–O4 are reported, not judged. They matter here because they show that
evidence and counted state can already disappear without a contract, and that
the stop conditions depend on which store they count.

## 2. Decision summary

| # | Decision |
| --- | --- |
| E1 | **Two stores, one owner per artifact** (§3). The public repository owns source; the private repository owns all execution evidence, `benchmark-history` (including the baseline pointers) and every automated benchmark issue. |
| E2 | **An explicit evidence destination**, declared in a repository-owned `evidence` block (repository identity and namespace allow-list, no credential). It is resolved at run time to a git remote that must be proven to be that repository and not the source (§4). There is no default and no fallback to `origin`. |
| E3 | **The publisher stays the publication-only workflow in the public repository.** It uses the same `benchmark-publication` App, installed on the evidence repository, and every token is scoped to the evidence repository only. Actions is disabled in the evidence repository (§6, Q1). |
| E4 | **`baselines/<lane>.json` is evidence** and moves with `benchmark-history`. Expected baselines in fixtures stay public (§8, Q2). |
| E5 | **Automated tracking, health, drift and missed-run issues move to the evidence repository.** After cutover the public repository receives no automated issue, comment or log content derived from evidence (§8, Q3). |
| E6 | **One namespace registry, one ruleset over `claude/**`** in the evidence repository. The public repository gets a no-bypass ruleset that blocks creating evidence-namespace refs (§8, Q4). |
| E7 | **An explicit remote is sufficient.** No storage abstraction or new backend is added. Git refs stay the storage, and ref names stay unchanged (§8, Q5). |
| E8 | **Records do not depend on where they are stored.** No sealed field names the evidence repository, so a migrated copy keeps its `content_sha256` and commit SHA. `provenance.repo` keeps naming the source (§7). |
| E9 | **One active store at a time**, selected by the manifest at the SHA a run checks out. Cutover and rollback go through drained, paused transitions (§10). |
| E10 | **#681 can merge, but its Routine is not activated until #688 and #689 land.** This keeps any concurrency evidence out of the public repository from the first run (§11). |

## 3. Ownership table

"Owner" is the repository that is authoritative for the artifact after cutover.
"Retention" is the rule the contract requires. A rule that differs from current
code is marked *new*.

### 3.1 Evidence (private: `amirbena/code-review-skill-evidence`)

| Namespace / artifact | Writer | Readers | Retention |
| --- | --- | --- | --- |
| `claude/benchmark-result-<run_id>` (staging seal: `benchmark-result.json`, `raw-bundle.json`) | Routine, through the seal (provider-mediated push) | publisher `sweep` (matching-refs and activity); `raw.location` resolution by a maintainer | Deleted by the publisher 30 days after its receipt (`DELETE_STAGING_REF`), and never before a receipt exists. Any other deletion needs maintainer approval recorded in an issue (*new*: O2 shows manual early deletion leaves `raw.location` dangling). |
| `claude/benchmark-handoff-check-<UTC>-<sha12>` (`handoff-check.json`) | Routine `auth-check` | maintainer only; never swept | The maintainer deletes it after reading the smoke-test result. No automatic deletion. |
| `claude/severity-observation-<run_id>` | Routine, `--trigger scheduled` | the entrypoint's stop condition and same-day guard (`ls-remote`); #653 analysis | Kept until #653 has read them (spec `removal_path`). Counted refs are never deleted while the Routine is enabled (*new*, invariant F7). |
| `claude/severity-trial-<run_id>` | manual or API runs of the same entrypoint | none (never counted) | Maintainer discretion. |
| `claude/concurrency-experiment-<run_id>` (planned, #681) | Routine, scheduled | the #681 stop condition (`ls-remote`); #682 analysis | Kept until #682 has read them (#683 removal path). The same rule as for severity refs applies. |
| `claude/concurrency-trial-<run_id>` (planned, #681) | manual or API runs | none (never counted) | Maintainer discretion. |
| `benchmark-history` → `records/<lane>/<yyyy>/<run_id>.json` | publisher App, create-only | execution (baseline record), publisher, watchdog | Never pruned. |
| `benchmark-history` → `receipts/<lane>/<yyyy>/<run_id>.json` | publisher App, create-only | publisher (already-published check), watchdog | Never pruned. |
| `benchmark-history` → `baselines/<lane>.json` | publisher App (bootstrap); maintainer (promotion) | execution (`GitRefHistory`), publisher | One pointer per lane; replaced only by explicit maintainer promotion. |
| Lane tracking issues (today #486, #487), health issue (#488), `benchmark-regression` drift issues, `benchmark-missed-run` issues, evidence and status comments | publisher App (`issues: write`) | maintainer; publisher (markers) | Issues are never deleted; they close under the existing lifecycle rules. |
| Labels `benchmark-regression`, `keep-open`, `benchmark-missed-run`, `benchmark-tracking` | maintainer (provisioning) | publisher | Provisioned in the evidence repository. The publisher still cannot create labels. |

### 3.2 Source (public: `amirbena/code-review-skill`)

| Artifact | Why it is source, not evidence |
| --- | --- |
| Entrypoints, publisher code, schemas, `benchmark-publish.yml` | code reviewed on `main` |
| `schedule/expected-run-manifest.json`, `schedule/*-spec.json` (including the new `evidence` block) | repository-owned configuration; identities only, no credentials |
| Fixtures and their **expected** findings (the "expected baselines"), corpus membership | the benchmark's definition, not an observation of a run |
| Development issues and PRs, docs, Wiki | development record. A maintainer may cite a private `run_id` in a development issue in their own words; nothing automated writes there (E5) |
| `main`, tags, release refs, harness development branches (`claude/issue-<n>-<hash>`) | source and release history. These `claude/` refs are agent working branches, not evidence |

### 3.3 Inventory check

The validation command for the acceptance criterion is to find every
benchmark ref prefix that code can write or read:

```bash
grep -rnE "claude/[a-z]" runtime_platform/benchmark .github/workflows --include='*.py' --include='*.json' --include='*.yml'
```

On `main` at `613fa43` it yields `claude/benchmark-result-`,
`claude/benchmark-handoff-check-`, `claude/severity-observation-` and
`claude/severity-trial-` (plus the generic confinement prefix `claude/` in
`benchmark_seal.py`, and test-only names). With #681's branch it adds
`claude/concurrency-experiment-` and `claude/concurrency-trial-`. Every other
`claude/` string in the repository is a path (`.claude/skills/`,
`.claude/agents/`, `distribution/claude/`), not a ref. All six prefixes are in
§3.1. #688 turns this grep into a policy test against the namespace registry
(F10).

## 4. Destination configuration contract

### 4.1 What the repository declares

The expected-run manifest gains one block, and each temporary spec
(severity, concurrency) refers to it rather than copying it:

```json
"evidence": {
  "repository": "amirbena/code-review-skill-evidence",
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

- `repository` is an **identity** (`owner/name`), never a URL with
  credentials, a token, or a key. It must differ from the manifest's top-level
  `repository`, which keeps naming the source.
- `namespaces` is the **allow-list** (the namespace registry). A producer may
  write only refs that start with a registered prefix. A new evidence namespace
  is added here in the same PR that introduces it (Q4).
- The exact key names are #688's choice. The semantics above are the contract.

### 4.2 What the run supplies

The entrypoints replace the defaulted `--seal-remote origin` with a
**required** evidence remote: a git remote name or URL supplied by the Routine
prompt for every non-dry run. The prompt template derives it from the evidence
repository the Routine cloned (O8); the exact form is experiment X1. Before
any fixture runs, the entrypoint must:

1. refuse a missing value. A dry run (`--seal-dir`) needs no remote;
2. resolve the value to a URL, and refuse it if the URL carries embedded
   credentials (`user:token@`). The URL is never printed unredacted;
3. prove identity: the URL's path must end in `evidence.repository`
   (optionally followed by `.git`). If it names the source repository, it is
   refused. A test-only override for a local bare repository is allowed, and it
   must be impossible to enable from a Routine prompt (for example, an
   environment variable that the test harness sets);
4. run a **preflight read** (`ls-remote` of `evidence.history_branch`). If
   that fails, the run stops with `evidence-store-unavailable` before any model
   cost is spent.

`GitRefHistory`, the severity and concurrency stop-condition reads, and the
seal all take the **same resolved destination**. A producer has no separate
remote argument that could diverge from the others.

### 4.3 What the publisher uses

The publisher's target repository is `evidence.repository`. It never comes
from `GITHUB_REPOSITORY` or from the top-level `repository`. Permalinks,
activity queries, matching-refs, contents, issues and the health issue all use
that one value.

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
| 2 | `evidence-destination-misconfigured` | missing value, credentials in the URL, identity mismatch, source repository named, or a ref outside the allow-list | stderr names the rule broken. The URL is redacted |
| 3 | `evidence-store-unavailable` | preflight, stop-condition read, push or read-back failed (unreachable, unauthorized, rejected) | The would-be sealed files are written to a local diagnostics directory (`--seal-dir` semantics). stdout carries a JSON status with `run_id`, the destination identity and the git error class, and the run counts as **unsealed** |

A non-zero exit never falls back to another destination and never claims
publication. The Routine prompt keeps its rule: on a non-zero exit, stop, do
not retry, and push nothing else. Local diagnostics are best-effort, because a
Routine sandbox does not outlive its session. The session transcript holding
stdout is the durable trace, and an unsealed run is still not evidence.

### 5.3 Publication side

| Operation | Contract |
| --- | --- |
| Read handoff | matching-refs and activity on `evidence.repository` with an App token |
| Persist / receipt / baseline bootstrap | create-only contents writes to `benchmark-history` on `evidence.repository` |
| Issues and comments | `evidence.repository` only |
| Watchdog history read | an App token with `contents: read` on `evidence.repository`. The job's `GITHUB_TOKEN` cannot read a private repository, so the current `BENCHMARK_READ_TOKEN=github.token` mapping changes |
| Failure | Token mint failure, 401/403/404 on the evidence repository, or an App-slug mismatch fails the job, with no write to any repository. There is no `--repository` override that could point at the source |

**Log hygiene** (*new*, because the workflow's logs are public): stdout and
stderr of `benchmark-publish.yml` may contain only run IDs, lane names, ref
names, counts, status and gate codes, and the acting identity. They must never
contain record fields, case results, drift observations, raw output, issue
bodies, or refusal `detail` text that quotes record content. Today the sweep
report goes to a runner temp file and the watchdog prints its report JSON to
stdout. #688 must make both satisfy this rule (F12).

## 6. Authentication boundaries

| Identity | Scope after cutover | Least-privilege rule | Verified? |
| --- | --- | --- | --- |
| **Routine** (provider-mediated, acting as the maintainer's connected GitHub access) | reads the source (clone); writes registered `claude/*` refs in the evidence repository; reads `benchmark-history` there | The Routine selects both repositories. No GitHub credential is provisioned into the runtime. The entrypoint writes only allow-listed refs to the proven destination. | **No.** Experiment X1. The docs say multiple repositories are supported. Whether the evidence clone's remote URL is usable from the source checkout, and whether access to a private repository requires the Claude GitHub App installed on it or a `/web-setup` grant, must be observed, not assumed. |
| **`benchmark-publication` App** | installed on the evidence repository. Tokens: `contents: write` (persist, delete staging), `issues: write`, `contents: read` (watchdog), each with `repositories: code-review-skill-evidence` only | never `actions`, `workflows`, `administration`, `pull-requests`, `secrets`, `environments` (unchanged). After cutover the public repository is removed from the installation. | Installation and minting are checked by #689. Activity-API access on a private repository is experiment X3. |
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
- source identity: `provenance.repo` = **the source repository**,
  `provenance.repo_sha`, `provenance.ref`, `provenance.entrypoint_version`;
- manifest or spec identity: `provenance.spec_sha256` for lanes. Observations
  and experiments record their spec identity in the same way;
- `runtime.model_id`, `runtime.runtime_name`, `runtime.runtime_version`,
  `runtime.adapter_id`;
- `started_at`, `finished_at`, `sealed_at` (UTC).

Rules:

- **No storage-location field in the sealed body** (E8). `raw.location` stays
  repository-relative (`<ref>:<file>`), so it resolves against whichever store
  holds the record. The evidence repository is implied by the manifest at
  `provenance.repo_sha`, so a reader can always derive it.
- The **receipt** may name the store (`record_permalink` is a URL into it).
  Receipts written before cutover keep their public URLs; they are immutable
  history, not rewritten.
- `provenance.repo` must never equal `evidence.repository` (F9).

## 8. Decisions on the open questions

### Q1 — Where the publisher runs, and which App and installation it uses

**Decision:** keep `benchmark-publish.yml` in the public repository, with the
same triggers (`schedule` and `workflow_dispatch`), the same `main`-only
`benchmark-publication` environment and the same App. Install the App on the
evidence repository and mint every token with
`repositories: code-review-skill-evidence`. Disable Actions in the evidence
repository.

**Rejected:**

- *Move the workflow into the evidence repository.* Its logs would be private,
  but the key would sit in a repository that LLM-session pushes reach, and on a
  Free plan there would be no deployment-branch policy to contain it (O9, §6).
  It would also move the workflow definition out of reach of the public policy
  tests.
- *A second App for the evidence repository.* Two installations with the same
  blast radius add rotation work and give no isolation, since the public
  repository receives no writes after cutover.
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
comments move to the evidence repository. At cutover, #690 has the maintainer
post a closing pointer on #486, #487 and #488 ("moved to the private evidence
store"), with no evidence content, and then close them. Public exposure after
that is limited to development issues a maintainer writes by hand, which may
cite a `run_id` and describe a regression in their own words. Public Actions
logs are bounded by the log-hygiene rule (§5.3).

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
- Public repository after cutover: one ruleset that **restricts creation** of
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
One declared identity, one required run-time remote that is proven against it,
and one publisher repository variable remove the defect. A storage abstraction
would add an interface with a single implementation, and an external store is
still the escape hatch defined in
[`canonical-result-and-persistence.md`](canonical-result-and-persistence.md)
§4.

## 9. Testable invariants

Each statement is phrased to be checkable by a unit or policy test against a
stubbed or bare-repository remote (#688), or by an observed check (#689).

**Failure**

- F1. A non-dry-run entrypoint invoked without an evidence remote exits 2 and
  pushes nothing.
- F2. An evidence remote that names the source repository, or that has
  embedded credentials, exits 2 before any fixture runs.
- F3. An unreachable or unauthorized evidence remote exits 3 before any
  fixture runs (preflight), and no ref is created on any remote.
- F4. A push or read-back failure exits 3, writes the would-be sealed files to
  the diagnostics directory, and leaves no ref on any remote, `origin`
  included.
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

- P1. `provenance.repo` equals the manifest's top-level `repository` and never
  `evidence.repository`.
- P2. No sealed artifact contains the evidence repository's identity or URL.
- P3. `run_id`, `repo_sha`, `model_id`, `runtime_version`, `spec_sha256` and
  the timestamps are present and unchanged in meaning (existing schema
  validation).

**Namespaces and scope**

- F8. A write to a ref outside `evidence.namespaces` is refused (exit 2).
- F9. The manifest validator rejects `evidence.repository == repository`.
- F10. Every `claude/<prefix>` constant in benchmark code is a registered
  namespace (the §3.3 grep as a policy test).
- F11. The publication workflow mints tokens only with
  `repositories: code-review-skill-evidence` after cutover, and never grants
  the permissions listed as "never" in §6.
- F12. Publisher stdout and stderr contain no record or issue-body content
  (asserted on fixture records containing sentinel strings).

**Rollback / migration**

- R1. At any commit of `main`, exactly one store is active: the manifest's
  `evidence.repository`.
- R2. No run crosses a cutover. A run's destination is a pure function of the
  manifest at its `repo_sha`.
- R3. The publisher sweeps exactly one store per pass.
- R4. No evidence ref is deleted from any store until its copy in the active
  store is verified (same SHA), and the deletion is approved in an issue.

## 10. Migration and rollback invariants (for #690)

**Cutover order:**

1. Pause every evidence-producing Routine.
2. Drain the old store: every staging ref there has a receipt.
3. Copy refs and `benchmark-history` by SHA (I4), and verify them.
4. Merge the manifest change.
5. Run one `auth-check` against the new store.
6. Re-enable the Routines.
7. Delete public refs only with recorded approval (R4).

The 12 commits in O3 are the inputs for step 3 for the refs already deleted
from `origin`. Re-pushing them preserves their SHAs. Copied, already-receipted
staging refs are recognized as published. Copied unreceipted refs are attested
by the migrating maintainer, who is in the allowlist, and this is why step 2
comes first.

**Counted refs.** The severity and concurrency stop conditions count the
active store. Before cutover the count must be equal in both stores, or the
campaign is paused until #690 copies the counted refs. O4 already violates
this on `origin`.

**Rollback** has two forms:

- **R-a, pause (preferred):** disable the Routines and fix forward. Nothing is
  published and no store changes.
- **R-b, revert the destination:** paused as in R-a, copy post-cutover
  evidence back by SHA, then revert the manifest commit. R-b republishes
  private evidence in the public repository, so it needs explicit maintainer
  approval recorded in an issue.

In both forms, two stores never accept writes at the same time: a run's
destination comes from its pinned manifest (R2), and the Routines are paused
across each transition.

## 11. Coordination with #680 (#681–#683)

- **Should `claude/concurrency-*` target the private repository from its
  first run? Yes.** The campaign is new evidence. Running it publicly would
  create exactly the evidence #686 sets out to remove, and would then need to
  be migrated.
- **Proposed dependency (not applied to the issues):** #681's
  *implementation* is not blocked and may merge first. Its Routine
  *activation*, the first step of #682's campaign, should be **blocked by
  #688 and #689**. #689 must include the two concurrency prefixes in its
  validation.
- **Interface note for #681:** its `prior_experiment_refs(remote)` and seal
  call follow the severity pattern. Whichever of #681 and #688 merges second
  routes them through the shared destination contract (§4.2). If #681 merges
  first, #688 adds the two prefixes to `evidence.namespaces` and replaces
  #681's `remote` argument. If #688 merges first, #681 adopts the contract
  before merging.
- **Sequencing:** #687 (this ADR) → #688 → #689 → #681 activation and #682
  campaign → #690 cutover of the lanes. #690 can run before or after the
  campaign. If it runs during the campaign, the counted-refs rule in §10
  applies.

## 12. Maintainer experiments (cannot be verified from the repository)

| # | Experiment | Decides |
| --- | --- | --- |
| X1 | A Routine selecting both repositories runs `git remote -v` in each clone and pushes one `claude/x1-*` ref to the private clone's remote from the source checkout. Then try a push to a non-`claude/` branch of the private repository. | the §4.2 supply mechanism; whether private access needs the Claude GitHub App on that repository; R1's real scope |
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
