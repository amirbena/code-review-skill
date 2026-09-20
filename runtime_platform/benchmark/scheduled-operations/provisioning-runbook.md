# Provisioning Runbook: `benchmark-publication` App, Environment, Rulesets, Labels

Part of the [scheduled benchmark operations decision record](decision-record.md)
(GitHub Issue [#464](https://github.com/amirbena/code-review-skill/issues/464)),
implementing follow-up **F7** as GitHub Issue
[#473](https://github.com/amirbena/code-review-skill/issues/473) (Epic
[#466](https://github.com/amirbena/code-review-skill/issues/466)) and
executed under [#484](https://github.com/amirbena/code-review-skill/issues/484).
A repository-development record, not packaged into either Skill archive.

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

### P6. Create the tracking and health issues

One tracking issue per scheduled lane (`sentinel`, `comprehensive`) and one
health issue. Evidence comments are pointers; the git record is the authority.
The threads are **not locked**: the App's installation token cannot comment on a
locked issue (observed in §4). The publisher instead counts only comments
authored by its own identity and treats any other comment as data
([`drift-issue-lifecycle-and-recovery.md`](drift-issue-lifecycle-and-recovery.md)
§3, A14).

```bash
for spec in "Benchmark evidence: sentinel lane" "Benchmark evidence: comprehensive lane" "Benchmark health status"; do
  gh issue create --repo $R --title "$spec" --label benchmark-tracking \
    --body "Written only by the \`benchmark-publication\` App (see runtime_platform/benchmark/scheduled-operations/). Comments from other accounts are ignored."
done
# then, for the health issue number returned:
gh issue pin <HEALTH_N> --repo $R
```

Verify — **expected** three open issues carrying the label, all `locked: false`,
and exactly the health issue pinned:

```bash
gh issue list --repo $R --label benchmark-tracking --state open --json number,title,labels
gh api repos/$R/issues/<N> --jq '{number, locked, state}'        # repeat for each
gh api graphql -f query='query{repository(owner:"amirbena",name:"code-review-skill"){pinnedIssues(first:5){nodes{issue{number title}}}}}'
```

If the issues were already created under the earlier procedure (locked, with the
"Locked to collaborators" body), unlock them and replace the body; the issue
numbers do not change:

```bash
for N in <SENTINEL_N> <COMPREHENSIVE_N> <HEALTH_N>; do
  gh issue unlock $N --repo $R
  gh issue edit   $N --repo $R --body "Written only by the \`benchmark-publication\` App (see runtime_platform/benchmark/scheduled-operations/). Comments from other accounts are ignored."
done
```

Then re-run the verify block above. Hand the three numbers to #469 (the manifest
carries the tracking-issue numbers) and #472 (health status).

### P7. Check the App comment lifecycle on a tracking issue

The publisher's evidence and health comments are authored by the App, so this
step proves the whole lifecycle under the App identity, in the order **POST →
verify author → PATCH the same comment → DELETE**. Mint a token narrowed to one
permission and use it for every call. The `${…:?}` guards abort on an unset or
empty value: an empty `GH_TOKEN` would make `gh` fall back to your own
credential and act as yourself, defeating the check (and the publisher has no
such fallback either).

```bash
export APP_SLUG=$(gh api repos/$R/installation -H "Authorization: Bearer $(mint_jwt)" --jq .app_slug)
TOKEN=$(gh api --method POST "app/installations/${INSTALL_ID:?run P2 first}/access_tokens" \
  -H "Authorization: Bearer $(mint_jwt)" \
  -f 'repositories[]=code-review-skill' -f 'permissions[issues]=write' --jq .token)
app() { GH_TOKEN="${TOKEN:?token mint failed}" gh api "$@"; }

# 1. POST
CID=$(app --method POST repos/$R/issues/<SENTINEL_N>/comments -f body='provisioning check (#484): created' --jq .id)
# 2. verify the stored author
app "repos/$R/issues/comments/${CID:?post failed}" --jq '{id, login: .user.login, type: .user.type, author_ok: (.user.login == (env.APP_SLUG + "[bot]"))}'
# 3. PATCH the same comment
app --method PATCH "repos/$R/issues/comments/${CID:?post failed}" -f body='provisioning check (#484): edited' --jq '{id, body, login: .user.login}'
# 4. DELETE
app --method DELETE "repos/$R/issues/comments/${CID:?post failed}"
unset TOKEN CID
```

**Expected:**

1. POST returns a comment id.
2. The stored comment reads `login` = `<APP_SLUG>[bot]`, `type` = `Bot`, and
   `author_ok: true`.
3. PATCH returns the same `id`, the edited `body`, and the same `login`.
4. DELETE succeeds with no output.

Anything else is a **stop condition**: a refused POST or PATCH (any `403`), an
`author_ok` other than `true`, a different `id` after PATCH, or a token that does
not mint. Stop and raise it on #466 before F8; do not retry under a personal
credential. The App token is never printed or pasted.

## 4. Observed evidence log

The maintainer fills one row per step **after performing it**, with the date, the
verification command run, and the observed output (or a link to it). Until a row
is filled the step is *not* complete, and #484's acceptance criteria are not met.

| Step | Performed (date, by) | Verification run | Observed result | Matches expected |
| --- | --- | --- | --- | --- |
| P1 labels | 2026-09-19, `amirbena` | P1 verify command, plus the colour/description listing | `["benchmark-missed-run","benchmark-regression","benchmark-tracking","keep-open"]`; colours and descriptions equal the manifest's `labels` (re-observed read-only at evidence time) | Yes |
| P2 App registered and installed (App ID, installation ID, slug) | 2026-09-19, `amirbena` | P2 verify output from the live provisioning session, before the local key was removed (maintainer-attested); App ID and bot user cross-checked read-only | `app_id` `5001454`, `app_slug` `benchmark-publication`, `installation_id` `163016436`, `repository_selection` `"selected"` (maintainer-attested). Re-observed: `Integration:5001454` is the bypass actor in the `benchmark-history` and `benchmark-staging-refs` rulesets; bot `benchmark-publication[bot]`, user id `331303104`, type `Bot`. The installation ID cannot be re-observed without the key | Yes (maintainer-attested) |
| P2 permission matrix equality | 2026-09-19, `amirbena` | P2 verify output from the live provisioning session (maintainer-attested); the App is private (`GET /apps/benchmark-publication` answers 404 without its key), so it is not re-observable here | `permissions` `{contents: write, issues: write, metadata: read}` and `permissions_match: true` (maintainer-attested); the amended P7 minted an installation token narrowed to `issues: write` | Yes (maintainer-attested) |
| P2 UI checks (installation scope, webhook, installability) | 2026-09-19, `amirbena` | Manual check of the GitHub App settings and installation page during the live provisioning session (maintainer-attested); the API cannot show these, and the key has since been removed | The installation is scoped to exactly `amirbena/code-review-skill`; the webhook is inactive; installation is restricted to "Only on this account" | Yes (maintainer-attested) |
| P3 environment branch policy | 2026-09-19, `amirbena` (environment created 14:35:20Z) | P3 verify commands | `{"protected_branches":false,"custom_branch_policies":true}` and `[{"name":"main","type":"branch"}]` | Yes |
| P4 environment secrets (names only) | 2026-09-19, `amirbena` | P4 verify commands | Environment `benchmark-publication`: `BENCHMARK_APP_ID` (updated 14:37:13Z) and `BENCHMARK_APP_PRIVATE_KEY` (14:37:25Z), no others; repository level: none listed | Yes |
| P5 `tags` ruleset | 2026-09-19, `amirbena` (14:38:28Z) | P5 verify loop | id `23700677`, `active`; refs `["~ALL"]`; rules `creation, deletion, update`; bypass `["Integration:4763596"]` | Yes |
| P5 `benchmark-history` ruleset | 2026-09-19, `amirbena` (14:39:31Z) | P5 verify loop | id `23700701`, `active`; refs `["refs/heads/benchmark-history"]`; rules `deletion, non_fast_forward, update`; bypass `["Integration:5001454","RepositoryRole:5"]` | Yes |
| P5 `benchmark-staging-refs` ruleset | 2026-09-19, `amirbena` (14:40:15Z) | P5 verify loop | id `23700709`, `active`; refs `["refs/heads/claude/benchmark-result-*"]`; rules `deletion, non_fast_forward` (no `creation`, no `update`); bypass `["Integration:5001454","RepositoryRole:5"]` | Yes |
| P5 `main` ruleset unchanged | re-observed 2026-09-19 | P5 last verify command | id `20558650`; bypass `["Integration:4763596","RepositoryRole:5"]`, no benchmark App; equals the §2 baseline | Yes |
| P6 tracking + health issues (numbers, unlocked, pinned) | 2026-09-19, `amirbena` (locked and #488 pinned 14:42Z; unlocked 15:05:30Z under A14) | P6 verify commands; the issues' timelines | #486 sentinel, #487 comprehensive, #488 health: each open, labelled `benchmark-tracking`, `locked: false`, canonical A14 body. #488 is pinned and the pinned-issues list is exactly #488: its timeline shows `pinned` 14:42:24Z, `unpinned` 15:09:52Z, `pinned` 15:22:02Z, `unpinned` 15:22:54Z, and `pinned` 15:25:45Z (all by `amirbena`), and it remained pinned when re-observed at 15:27Z | Yes |
| P7 App comment lifecycle (POST → author → PATCH → DELETE) | 2026-09-19, `amirbena`, on #486 | Amended P7 with an installation token narrowed to `issues: write` | Reported by the maintainer: token minted; POST returned comment id `5742925037`; stored author `benchmark-publication[bot]`, type `Bot`, `author_ok: true`; PATCH returned the same id with body `provisioning check (#484): edited`; DELETE succeeded; no personal credential used. Re-observed read-only: `GET` of that comment answers 404 and #486 has 0 comments | Yes |

Rows marked *maintainer-attested* record checks made during the live provisioning session that cannot be re-observed without the App private key, which was removed after P7 and is not regenerated to re-observe P2.

### Recorded deviations

Observed results that did **not** match the expected outcome. They are evidence,
not failures to hide, and each names its disposition.

| Step | Performed (date, by) | Verification run | Observed result | Matches expected | Disposition |
| --- | --- | --- | --- | --- | --- |
| P7 as first specified (App write to a locked issue) | 2026-09-19, `amirbena` | POST `repos/$R/issues/486/comments` on the locked sentinel tracking issue, with a `benchmark-publication` installation token narrowed to `issues: write`; the token minted successfully and no personal credential was used | `HTTP 403: Unable to create comment because issue is locked`; no comment was created; the token was discarded | **No** — the stop condition above fired | The locked-thread design is replaced by publisher-author filtering (A14, [#489](https://github.com/amirbena/code-review-skill/issues/489); approved on [#466](https://github.com/amirbena/code-review-skill/issues/466#issuecomment-5742792835)). P6 and P7 above are the amended procedure; the amended P7 passed on 2026-09-19 (P7 row). |

## 5. Handoffs and open reconciliations

| Item | Owner | State |
| --- | --- | --- |
| Tracking-issue label name (`benchmark-tracking`) and label definitions | #469 (F3) | reconciled: the manifest matches P1 |
| Tracking and health issue numbers | #469 (manifest), #472 (health status) | produced by P6: sentinel #486, comprehensive #487, health #488; recorded in the manifest |
| Secret names `BENCHMARK_APP_ID`, `BENCHMARK_APP_PRIVATE_KEY` (proposed) | #474 (F8) | workflow must match P4 |
| Publisher-author filtering (A14): marker recognition and status-comment lookup count only comments authored by `<app-slug>[bot]`, on tracking, health, and drift issues | #471 (F5), #472 (F6) | contract landed by #489; implemented and tested for drift and tracking issues by #471 ([`../publication-cli.md`](../publication-cli.md) §4), status-comment lookup pending in #472 |
| Tracking and health issues created locked under the earlier procedure | maintainer, under #484 | done 2026-09-19: unlocked, bodies replaced, amended P7 passed; issue numbers unchanged; #488's pin still to be restored |
| `benchmark-history` branch does not exist yet, and `creation` is not restricted by the design table, so the first writer of the branch is whoever pushes it first; the intended first writer is the publisher's first pass | maintainer decision | decided 2026-09-19, option (a): leave the branch absent; the publisher's first successful publication creates it. No manual seeding and no `creation` rule. Observed: `main` is the only branch on the remote |
| `docs/RELEASE.md` documents the release App only as a `main` bypass actor; the live ruleset also lists Admin (E16) | out of scope here | unchanged |

## 6. Rollback

Everything above is reversible without touching repository content: delete the
three new rulesets (`gh api --method DELETE repos/$R/rulesets/<id>`), delete the
environment (this removes its secrets), uninstall or delete the App (revokes its
tokens), and close the tracking issues. Deleting the App or its key is
also the credential-revocation path drilled in #474. Do not delete labels that
open issues still carry.
