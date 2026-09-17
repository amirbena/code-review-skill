# Class 2 Cloud Routine Integration

Repository-development doc for GitHub Issue
[#415](https://github.com/amirbena/code-review-skill/issues/415), the
implementation issue
[`runtime-execution-contract.md`](runtime-execution-contract.md) §2.2/§8
scopes but does not itself implement. Like the rest of [`./`](README.md),
this is **not packaged into either Skill archive**, and no packaged Skill
resource depends on it.

This document fixes the concrete Claude Cloud Routine integration for
Class 2 (maintainer-controlled, optional quality observability —
`runtime-execution-contract.md` §2.2/§4.3). It does not redefine that
contract; a genuine contradiction discovered here is resolved by updating
`runtime-execution-contract.md`, not by silently deviating in this
document or in code.

## 1. Vehicle, not policy

This issue builds the Routine **vehicle**
[#338](https://github.com/amirbena/code-review-skill/issues/338) and
[#339](https://github.com/amirbena/code-review-skill/issues/339) schedule
and run inside — it owns no baseline/history policy, no drift-vs-noise
policy, and no GitHub issue open/comment/close lifecycle. It produces one
thing: verified, attributable evidence for one run, persisted somewhere
#338/#339 can read it. Selection logic (which case ids to run) is never
computed here either — [#333](https://github.com/amirbena/code-review-skill/issues/333)/[#334](https://github.com/amirbena/code-review-skill/issues/334)
own that; this vehicle only accepts a case-id list.

## 2. Pipeline

```text
Claude Cloud Routine (maintainer-configured; on-demand or scheduled)
  → fresh checkout of the target ref (default: main)
  → record the checked-out SHA (git rev-parse HEAD)
  → python3 scripts/benchmark/run_benchmark_routine.py --mode <mode> ...
      → run_benchmark.py (unmodified §3 execution contract, once per case)
      → benchmark_routine_verify.verify_benchmark_output (positive
        completion check — never trusts the Routine's own "green" status)
      → on any unverified run: fail closed, exit non-zero, post nothing
      → on a verified run: post evidence as a comment on a maintainer-
        owned tracking GitHub Issue (§4), never into the Routine's own
        transcript/run history
```

`run_benchmark_routine.py` (`scripts/benchmark/run_benchmark_routine.py`)
is the only new execution-path code. It never re-implements
`run_benchmark.py`, the runner, the matcher, or the adapter — it shells
out to the existing `run_benchmark.py` CLI once per requested case id and
inspects its stdout.

### 2.1 Modes

Built on `run_benchmark.py`'s existing `--case-id` surface (§9 of
`runtime-execution-contract.md`'s parent contract; no new selection logic
is added here) plus, for `comprehensive`, programmatic corpus-membership
discovery added by #431
(`scripts/benchmark/benchmark_corpus_membership.py`):

| Mode | Case ids | Use |
| --- | --- | --- |
| `smoke` | one or a few explicit `--case-id` values | sanity-check the Routine itself |
| `selected` | whatever `--case-id` list is handed to it (e.g. a future #334 Top-K output) | PR-time-adjacent observability, never a merge gate |
| `sentinel` | none — runs the whole `--corpus-dir` (non-recursive: the 4 permanent canonical cases) | scheduled sentinel lane, every 3 days (#431) |
| `comprehensive` | none — runs every `benchmark-case/v2` fixture discovered recursively under `--corpus-dir` | scheduled comprehensive lane, weekly/Friday (#431) |
| `full` | none — **deprecated fixed synonym for `sentinel`** (#431) | kept, unchanged in behavior, only for backward compatibility with existing Routine prompt configuration; emits a stderr deprecation notice; new configuration must use `sentinel` explicitly. Never means `comprehensive`. |
| `auth-check` | none — no benchmark run | GitHub auth/issue-permission smoke test (§5) |

`sentinel` and `comprehensive` are the two-tier scheduled execution lanes
`docs/benchmark/corpus/README.md` and
`docs/benchmark/nightly-history-and-baseline.md` §2 define; `full`'s
pre-#431 ambiguity (it happened to only ever resolve to the 4 top-level
cases, because `--corpus-dir`'s glob is non-recursive) is resolved by this
table, not left as a second live meaning.

## 3. Positive completion verification

`scripts/benchmark/benchmark_routine_verify.py::verify_benchmark_output`
is the fail-closed check. It never treats a non-zero exit, unparseable
stdout, a missing/malformed per-case result shape
(`docs/benchmark/runner-contract.md` §6), or any case whose `status` is
not `"executed"` as passing evidence — including the
`check_runtime_available` preflight-failure path, which exits non-zero
with no stdout JSON at all. Unit-tested fail-closed in
[`../../tests/unit/benchmark/test_benchmark_routine_verify.py`](../../tests/unit/benchmark/test_benchmark_routine_verify.py):
a forced `error`/`runtime-unavailable` case is proven to flag, not
silently pass.

`run_benchmark_routine.py` runs one `run_benchmark.py` invocation per
requested case id (so a single case's failure is individually visible)
and requires every invocation in the batch to verify before posting any
evidence — a partial pass is still an overall fail-closed non-passing
run.

## 4. Evidence persistence

Evidence is posted as a comment on a maintainer-owned **tracking GitHub
Issue**, not committed into the repository and not left in the Routine's
own transcript/run history:

- durable and inspectable independent of Routine run retention (§2.2,
  undocumented Routine-side retention was the reason this document rejects
  relying on it — see "Rejected" below);
- GitHub-native, so [#338](https://github.com/amirbena/code-review-skill/issues/338)
  (history/baseline) and [#339](https://github.com/amirbena/code-review-skill/issues/339)
  (drift/issue lifecycle) can consume it with the `gh`/GitHub API access
  they already need for their own issue lifecycle, without a second
  storage mechanism;
- never reachable from contributor PR automation — the tracking Issue is
  written to only by the maintainer's own Routine invocation, exactly like
  every other Class 2 credential/identity boundary (§2.2).

Each evidence comment is a fenced JSON block containing:

```json
{
  "metadata": {
    "mode": "smoke",
    "repo_sha": "<checked-out SHA>",
    "runtime_name": "<CLI name>",
    "runtime_version": "<CLI version>",
    "model_id": "<explicit model/backend id>",
    "timestamp": "<UTC ISO-8601>"
  },
  "overall_verified": true,
  "runs": [ { "passed": true, "reason": "verified", "case_count": 1, "case_ids": ["..."] } ]
}
```

matching `runtime-execution-contract.md` §5's required metadata set. The
maintainer creates the tracking Issue once (or lets the first Routine run
create it via `--evidence-issue` omitted) and passes its number as
`--evidence-issue` on every later invocation, so evidence accumulates as a
single, chronologically ordered comment thread rather than one issue per
run.

### Rejected: evidence committed to the repository

Pushing evidence JSON files directly into the repository from an
unattended Routine run was considered and rejected: it would bypass this
repository's own PR-review workflow
([`../../policies/git-pr-merge-policy.md`](../../policies/git-pr-merge-policy.md))
for every scheduled run, which is a larger, harder-to-audit surface than a
GitHub Issue comment thread scoped to evidence data only.

## 5. GitHub auth/issue-permission smoke test

`--mode auth-check` proves GitHub issue create/comment permissions work
from inside the Routine's own execution context, independent of any
benchmark run — it posts (creates or comments on) the same tracking Issue
with a timestamped marker and nothing else. Run this once whenever the
Routine's credentials/identity change, and before the first scheduled
`full`/nightly run relies on unattended evidence posting.

## 6. Metadata: explicit, not auto-detected

Per `runtime-execution-contract.md` §5's own wording, neither the
runtime/model identity nor the Skill/repository SHA is automatic in a
Cloud Routine. `run_benchmark_routine.py`:

- resolves `repo_sha` itself (`git rev-parse HEAD` in the fresh checkout —
  this one *is* mechanically derivable);
- accepts `--runtime-name` / `--runtime-version` with a best-effort
  `<cli> --version` probe fallback, since the CLI executable is already
  known;
- requires the Routine prompt to pass `--model-id` explicitly — no
  reliable in-process signal exists for which model backend served a given
  Cloud Routine run, so this document does not pretend one does.

## 7. Credential / usage bounding

Execution runs entirely under the maintainer's own already-authorized
Claude Cloud Routine session and `gh` identity — no separately provisioned,
repository-level, independently-revocable secret (§2.2/§4.3; this is a
deliberate consequence of Class 2's trust boundary, not an oversight). The
maintainer configuring a schedule is responsible for sizing run frequency
and corpus scope (`smoke` vs. `full`) against their Claude subscription
usage and the account's Routine run limits — this document does not fix a
specific schedule, only the vehicle a schedule invokes.

## 8. Non-reachability from contributor automation

Nothing in this document's pipeline is invoked by `.github/workflows/**`
or any other repository-triggered automation — there is no independent
GitHub Actions benchmark execution path left over from the retired #255
workflow (#420) for it to couple to. `run_benchmark_routine.py` is dead
code from the contributor-PR path's perspective — it is only ever invoked
by a maintainer-configured Cloud Routine prompt (§9) or by a maintainer
running it locally by hand. `docs/benchmark/selection.md`'s existing
non-blocking, informational-only contributor path (#334) is unchanged by
this document.

## 9. Routine prompt template

The literal instructions a maintainer pastes into a Claude Cloud Routine's
own task/schedule definition (outside this repository — Cloud Routines are
configured through Claude's own product surface, not a repository file
that executes automatically):

```text
1. Check out a fresh copy of amirbena/code-review-skill at <ref, default main>.
2. Install dev dependencies (pip install -r requirements-dev.txt).
3. Run:
   python3 scripts/benchmark/run_benchmark_routine.py \
     --mode <smoke|selected|sentinel|comprehensive|auth-check> \
     [--case-id <id> ...] \
     --evidence-issue <tracking issue number> \
     --model-id <the model backend this Routine session is running as>
4. If the command exits non-zero, stop — do not report success, do not
   retry silently, and do not post anything else to GitHub. The evidence
   issue already reflects nothing (fail-closed: no comment was posted).
5. If it exits zero, the evidence comment has already been posted by the
   script itself. Nothing further to do.
```

### 9.1 Two lanes, two Cloud Routine schedules (#431)

The sentinel and comprehensive lanes (§2.1) are **two separate Cloud
Routine schedule configurations**, each pasting the template above with
its own `--mode` and its own recurrence, both targeting a **01:00
Israel-local start / 04:00 maximum-completion** window
(`docs/benchmark/nightly-history-and-baseline.md` §2). Timezone/DST
handling for that window is entirely a Cloud Routine scheduling-
configuration responsibility — set the schedule in Israel local time (or
in UTC with the correct seasonal offset) in the Routine's own product
surface; nothing in `scripts/benchmark/` computes, stores, or adjusts for
a timezone.

| Lane | `--mode` | Recurrence |
| --- | --- | --- |
| Sentinel | `sentinel` | every 3 days |
| Comprehensive | `comprehensive` | weekly, Friday night |

**Collision is expected and never deduplicated.** Every 3 days and weekly
will periodically land on the same night; when they do, both Routine runs
execute, verify, and post evidence independently — each against its own
`--evidence-issue` thread and its own keyed baseline
(`nightly-history-and-baseline.md` §4). This issue does not merge, skip,
or otherwise deduplicate a same-night collision.

## 10. Non-goals (restated from the parent Issue)

No drift-vs-noise policy, no regression fingerprinting, no GitHub issue
open/comment/close *lifecycle* (only a flat evidence-comment append), no
full-corpus baseline/history storage schema, no nightly scheduling
*policy* decision, no PR-time taxonomy/Top-K selection logic, and no
re-opening of Class 1 provisioning. All owned elsewhere per
`runtime-execution-contract.md` and the parent Issue's own Non-Goals
section.

## 11. Addendum: `--results-out` for nightly history (#338)

[#338](https://github.com/amirbena/code-review-skill/issues/338) added an
optional `--results-out PATH` flag to `run_benchmark_routine.py`: on a
verified run only, it writes the concatenated raw per-invocation
`run_benchmark.py` output to that path, for
[`nightly-history-and-baseline.md`](nightly-history-and-baseline.md) to
persist. Omitting it (every call site that existed before #338) is
unaffected — this is additive, not a change to the modes, verification,
or evidence-issue behavior above.
