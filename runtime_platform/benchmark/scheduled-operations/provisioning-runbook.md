# Provisioning Runbook: `benchmark-publication` App, Environment, Rulesets, Labels

Part of the [scheduled benchmark operations decision record](decision-record.md)
(GitHub Issue [#464](https://github.com/amirbena/code-review-skill/issues/464)),
implementing follow-up **F7** as GitHub Issue
[#473](https://github.com/amirbena/code-review-skill/issues/473) (Epic
[#466](https://github.com/amirbena/code-review-skill/issues/466)). A
repository-development record, not packaged into either Skill archive.

**Ownership.** The steps below are repository and account administration,
performed **only by the maintainer**; a coding agent does not register the App,
change permissions, create rulesets, or handle the App key. This file is the
repository-owned half of F7: the exact procedure, the expected result of every
step, and the log where the maintainer records what was observed.

The design being provisioned is fixed by
[`execution-publication-boundary.md`](execution-publication-boundary.md) §6–§7,
[`publication-architecture.md`](publication-architecture.md) §4, and
[`drift-issue-lifecycle-and-recovery.md`](drift-issue-lifecycle-and-recovery.md)
§3. This runbook does not restate their rationale and changes none of their
decisions.

**Order matters.** [`follow-up-plan.md`](follow-up-plan.md) §2: the publication
workflow (F8, #474) is enabled only after this runbook is complete, so the App
secrets, environment, and rulesets exist first. Nothing here schedules or runs
the benchmark.

## 1. Conventions

```bash
export R=amirbena/code-review-skill
```

- Every step has an **expected** result. A step is complete only when its
  verification command was run and the output matched (§4 records it).
- Verify by inspecting live state with `gh api`; do not treat a UI page you just
  saved as proof.
- **Never record** a private key, a JWT, an installation token, or a secret
  value in this file, an issue, or a PR. App and installation IDs are not
  secrets and are recorded. `gh secret list` shows names only.
- `benchmark-publication` is a **dedicated** App. Do not reuse or edit the
  release App (`RELEASE_APP_ID`).

## 2. Observed state before provisioning (2026-09-19)

Read-only queries against `amirbena/code-review-skill`, run as `amirbena`
(admin), before any step below. This is the baseline the post-checks are compared
against.

| Surface | Observed | Query |
| --- | --- | --- |
| Rulesets | one: `main` (id `20558650`, `active`, branch target) | `gh api repos/$R/rulesets` |
| `main` ruleset rules | `deletion`, `non_fast_forward`, `pull_request`, `required_status_checks` | `gh api repos/$R/rulesets/20558650 --jq '[.rules[].type]'` |
| `main` bypass actors | `RepositoryRole:5` (Admin), `Integration:4763596` (release App), both `always` | same, `--jq '.bypass_actors'` |
| Environments | one: `release`, no protection rules, no branch policy | `gh api repos/$R/environments` |
| Benchmark-related labels | none exist | `gh label list --limit 200` |
| `benchmark-history` branch | does not exist; no other non-`main` branch | `git ls-remote --heads origin` |
| Tags | 72 exist; no tag ruleset | `git ls-remote --tags origin \| grep -vc '\^{}$'` (a plain line count gives 143 because each annotated tag also lists a peeled `^{}` ref) |
| Benchmark App installation | not observable with a user token (`GET /repos/$R/installation` answers 401 without an App JWT); [E16](decision-record.md) records no such App | `gh api repos/$R/installation` |

## 3. Steps

### P1. Create the labels

Labels are a provisioning prerequisite: the publisher has no label-creation
capability and fails closed at start-up if one is missing (A10).

```bash
gh label create benchmark-regression  --repo $R --color b60205 --description "Confirmed scheduled-benchmark drift (one issue per fingerprint)"
gh label create keep-open             --repo $R --color 5319e7 --description "Maintainer hold: never auto-close this benchmark issue"
gh label create benchmark-missed-run  --repo $R --color d93f0b --description "A scheduled benchmark lane exceeded its max gap"
gh label create benchmark-tracking    --repo $R --color 1d76db --description "Per-lane evidence thread or health status for the scheduled benchmark"
```

Verify — **expected** `["benchmark-missed-run","benchmark-regression","benchmark-tracking","keep-open"]`:

```bash
gh label list --repo $R --limit 200 --json name --jq '[.[].name | select(test("^(benchmark-(regression|missed-run|tracking)|keep-open)$"))] | sort'
```

The four names, colors, and descriptions above are the manifest's `labels`
([`../schedule-spec.md`](../schedule-spec.md) §3, #469); a test keeps these
commands in step with it.

### P2. Register the App

GitHub → Settings → Developer settings → GitHub Apps → New GitHub App:

- Name `benchmark-publication` (any free name, recorded in §4); no user-facing
  homepage needed beyond the repository URL.
- Webhook: **inactive**. No callback URL, no user authorization, no
  device flow.
- Repository permissions: **`Contents: Read and write`, `Issues: Read and
  write`, `Metadata: Read-only`** (implicit) — and nothing else. In particular
  never `Actions`, `Workflows`, `Administration`, `Pull requests`, `Secrets`, or
  `Environments`.
- Installable by: **Only on this account**.
- Generate one private key; keep it out of the repository and out of shell
  history (a local file with `chmod 600`, kept until P7 is done — P7 and any
  re-check mint a fresh JWT from it — then deleted or moved to a password
  manager).

Install it on **only** `amirbena/code-review-skill` (Only select repositories).

To verify with `gh`, build an App JWT locally from the key. A JWT lives at most
10 minutes, so mint one **per use** with the function below rather than reusing
a variable. The JWT is a credential: never paste it anywhere.

```bash
export APP_ID=<App ID>  KEY_PEM=/path/to/private-key.pem
b64() { openssl base64 -A | tr '+/' '-_' | tr -d '='; }
mint_jwt() {
  local now h p s
  now=$(date +%s)
  h=$(printf '{"alg":"RS256","typ":"JWT"}' | b64)
  p=$(printf '{"iat":%d,"exp":%d,"iss":"%s"}' $((now-60)) $((now+540)) "$APP_ID" | b64)
  s=$(printf '%s.%s' "$h" "$p" | openssl dgst -sha256 -sign "$KEY_PEM" | b64)
  printf '%s.%s.%s' "$h" "$p" "$s"
}
```

Verify — **expected** `permissions_match: true` (the matrix equals the boundary
document's §7 exactly, checked as an equality, not eyeballed) and
`repository_selection: "selected"`:

```bash
gh api repos/$R/installation -H "Authorization: Bearer $(mint_jwt)" --jq '{
  app_slug, app_id, installation_id: .id, repository_selection, permissions,
  permissions_match: (.permissions == {"contents":"write","issues":"write","metadata":"read"})}'
export INSTALL_ID=$(gh api repos/$R/installation -H "Authorization: Bearer $(mint_jwt)" --jq .id)
```

This also yields the App ID (rulesets) and the installation ID (`$INSTALL_ID`,
used by P7 and recorded in §4). Confirm in Settings → Integrations → the App →
Configure that exactly one repository is selected.

### P3. Create the environment, default-branch-only

```bash
gh api --method PUT repos/$R/environments/benchmark-publication --input - <<'JSON'
{"deployment_branch_policy":{"protected_branches":false,"custom_branch_policies":true}}
JSON
gh api --method POST repos/$R/environments/benchmark-publication/deployment-branch-policies -f name=main -f type=branch
```

Verify — **expected** `{"protected_branches":false,"custom_branch_policies":true}`
and `[{"name":"main","type":"branch"}]` (the default branch is `main` today; if it
is ever renamed, update the policy):

```bash
gh api repos/$R/environments/benchmark-publication --jq '.deployment_branch_policy'
gh api repos/$R/environments/benchmark-publication/deployment-branch-policies --jq '[.branch_policies[] | {name,type}]'
```

### P4. Store the App credentials in the environment

The names below are **proposed** to mirror the release App's `RELEASE_APP_ID` /
`RELEASE_APP_PRIVATE_KEY`; the workflow that consumes them is #474 (F8) and
must use whatever is recorded here.

```bash
gh secret set BENCHMARK_APP_ID          --env benchmark-publication --repo $R --body "$APP_ID"
gh secret set BENCHMARK_APP_PRIVATE_KEY --env benchmark-publication --repo $R < "$KEY_PEM"
```

Keep the local key file until P7 is finished, then delete it or move it to the
maintainer's password manager; it is never on the execution side and never in
the repository.

Verify — **expected** exactly the two names, and none at repository level:

```bash
gh secret list --env benchmark-publication --repo $R
gh secret list --repo $R          # must not contain BENCHMARK_APP_*
```

### P5. Create the rulesets

Substitute `$APP_ID`. Admin is `RepositoryRole:5`, the same identifier the live
`main` ruleset uses. The benchmark App is **never** added to `main`.

**Tags** — `contents: write` would otherwise let the App create or move tags;
only the release App may:

```bash
gh api --method POST repos/$R/rulesets --input - <<'JSON'
{"name":"tags","target":"tag","enforcement":"active",
 "conditions":{"ref_name":{"include":["~ALL"],"exclude":[]}},
 "bypass_actors":[{"actor_id":4763596,"actor_type":"Integration","bypass_mode":"always"}],
 "rules":[{"type":"creation"},{"type":"update"},{"type":"deletion"}]}
JSON
```

**`benchmark-history`** — single writer; Admin bypass exists so the maintainer
can promote a baseline with their own credentials (decision M7):

```bash
gh api --method POST repos/$R/rulesets --input - <<JSON
{"name":"benchmark-history","target":"branch","enforcement":"active",
 "conditions":{"ref_name":{"include":["refs/heads/benchmark-history"],"exclude":[]}},
 "bypass_actors":[{"actor_id":$APP_ID,"actor_type":"Integration","bypass_mode":"always"},
                  {"actor_id":5,"actor_type":"RepositoryRole","bypass_mode":"always"}],
 "rules":[{"type":"update"},{"type":"deletion"},{"type":"non_fast_forward"}]}
JSON
```

**Sealed staging refs** — deletion and force-push protection only. Creation and
update stay **open**: the Routine's provider-native push authenticates as the
maintainer, not as the App.

```bash
gh api --method POST repos/$R/rulesets --input - <<JSON
{"name":"benchmark-staging-refs","target":"branch","enforcement":"active",
 "conditions":{"ref_name":{"include":["refs/heads/claude/benchmark-result-*"],"exclude":[]}},
 "bypass_actors":[{"actor_id":$APP_ID,"actor_type":"Integration","bypass_mode":"always"},
                  {"actor_id":5,"actor_type":"RepositoryRole","bypass_mode":"always"}],
 "rules":[{"type":"deletion"},{"type":"non_fast_forward"}]}
JSON
```

Verify — **expected** the four rulesets below, all `active`; the rule list of
each equal to the design table; and `main` unchanged from §2:

```bash
gh api repos/$R/rulesets --jq '[.[] | {name,target,enforcement}]'
for n in tags benchmark-history benchmark-staging-refs; do
  id=$(gh api repos/$R/rulesets --jq ".[] | select(.name==\"$n\") | .id")
  gh api repos/$R/rulesets/$id --jq '{name, refs: .conditions.ref_name.include, rules: ([.rules[].type]|sort), bypass: ([.bypass_actors[]|"\(.actor_type):\(.actor_id)"]|sort)}'
done
gh api repos/$R/rulesets/20558650 --jq '[.bypass_actors[]|"\(.actor_type):\(.actor_id)"]|sort'
```

Expected per ruleset:

| Ruleset | refs | rules | bypass |
| --- | --- | --- | --- |
| `tags` | `~ALL` | `creation`, `deletion`, `update` | `Integration:4763596` |
| `benchmark-history` | `refs/heads/benchmark-history` | `deletion`, `non_fast_forward`, `update` | `Integration:<APP_ID>`, `RepositoryRole:5` |
| `benchmark-staging-refs` | `refs/heads/claude/benchmark-result-*` | `deletion`, `non_fast_forward` (**no** `creation`, **no** `update`) | `Integration:<APP_ID>`, `RepositoryRole:5` |
| `main` (id `20558650`) | unchanged | unchanged | `["Integration:4763596","RepositoryRole:5"]` — **no benchmark App** (E16) |

These are inspection checks. Behavioral proof (a publication pass writing
`benchmark-history` under the App, and a refused non-App write) belongs to the
F8 drills (#474), because the maintainer is an Admin bypass actor and cannot
demonstrate a refusal from their own account.

### P6. Create and lock the tracking and health issues

One tracking issue per scheduled lane (`sentinel`, `comprehensive`) and one
health issue. Evidence comments are pointers; the git record is the authority, so
each thread is locked to collaborators.

```bash
for spec in "Benchmark evidence: sentinel lane" "Benchmark evidence: comprehensive lane" "Benchmark health status"; do
  gh issue create --repo $R --title "$spec" --label benchmark-tracking \
    --body "Written only by the \`benchmark-publication\` App (see runtime_platform/benchmark/scheduled-operations/). Locked to collaborators; do not comment."
done
# then, for each issue number N returned:
gh issue lock <N> --repo $R
gh issue pin  <HEALTH_N> --repo $R      # health issue only
```

Verify — **expected** three open issues carrying the label, all `locked: true`,
and exactly the health issue pinned:

```bash
gh issue list --repo $R --label benchmark-tracking --state open --json number,title,labels
gh api repos/$R/issues/<N> --jq '{number, locked, state}'        # repeat for each
gh api graphql -f query='query{repository(owner:"amirbena",name:"code-review-skill"){pinnedIssues(first:5){nodes{issue{number title}}}}}'
```

Hand the three numbers to #469 (the manifest carries the tracking-issue numbers)
and #472 (health status).

### P7. Check that the App can write a locked tracking issue (recommended)

The design assumes the App's `issues: write` lets it comment on a locked thread
(*expected but not demonstrated* until now). Mint a token narrowed to one
permission, post, and remove the comment:

```bash
TOKEN=$(gh api --method POST "app/installations/${INSTALL_ID:?run P2 first}/access_tokens" \
  -H "Authorization: Bearer $(mint_jwt)" \
  -f 'repositories[]=code-review-skill' -f 'permissions[issues]=write' --jq .token)
GH_TOKEN="${TOKEN:?token mint failed}" gh api --method POST repos/$R/issues/<SENTINEL_N>/comments -f body='provisioning check (#473); will be removed' --jq '{id, user: .user.login}'
GH_TOKEN="${TOKEN:?token mint failed}" gh api --method DELETE repos/$R/issues/comments/<id>
unset TOKEN
```

The `${…:?}` guards abort on an unset or empty value: an empty `GH_TOKEN` would
otherwise make `gh` fall back to your own credential and post the comment as
yourself, defeating the check.

**Expected** `user` = `benchmark-publication[bot]` (anything else means the App
token was not used) and the delete succeeds with no output. If the write is
refused on a locked issue, stop and raise it on #466 before F8: the "locked to
collaborators" design would need changing, not this runbook.

## 4. Observed evidence log

The maintainer fills one row per step **after performing it**, with the date, the
verification command run, and the observed output (or a link to it). Until a row
is filled the step is *not* complete, and #473's acceptance criteria are not met.

| Step | Performed (date, by) | Verification run | Observed result | Matches expected |
| --- | --- | --- | --- | --- |
| P1 labels | pending | | | |
| P2 App registered and installed (App ID, installation ID, slug) | pending | | | |
| P2 permission matrix equality | pending | | | |
| P3 environment branch policy | pending | | | |
| P4 environment secrets (names only) | pending | | | |
| P5 `tags` ruleset | pending | | | |
| P5 `benchmark-history` ruleset | pending | | | |
| P5 `benchmark-staging-refs` ruleset | pending | | | |
| P5 `main` ruleset unchanged | pending | | | |
| P6 tracking + health issues (numbers, locked, pinned) | pending | | | |
| P7 App write to a locked issue | pending | | | |

## 5. Handoffs and open reconciliations

| Item | Owner | State |
| --- | --- | --- |
| Tracking-issue label name (`benchmark-tracking`) and label definitions | #469 (F3) | reconciled: the manifest matches P1 |
| Tracking and health issue numbers | #469 (manifest), #472 (health status) | produced by P6 |
| Secret names `BENCHMARK_APP_ID`, `BENCHMARK_APP_PRIVATE_KEY` (proposed) | #474 (F8) | workflow must match P4 |
| `benchmark-history` branch does not exist yet, and `creation` is not restricted by the design table, so the first writer of the branch is whoever pushes it first; the intended first writer is the publisher's first pass | maintainer decision | decide whether to seed the orphan branch at provisioning or add a `creation` rule (a stricter reading than the design table) |
| `docs/RELEASE.md` documents the release App only as a `main` bypass actor; the live ruleset also lists Admin (E16) | out of scope here | unchanged |

## 6. Rollback

Everything above is reversible without touching repository content: delete the
three new rulesets (`gh api --method DELETE repos/$R/rulesets/<id>`), delete the
environment (this removes its secrets), uninstall or delete the App (revokes its
tokens), and unlock/close the tracking issues. Deleting the App or its key is
also the credential-revocation path drilled in #474. Do not delete labels that
open issues still carry.
