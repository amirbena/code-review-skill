# Class 2 Cloud Routine Integration

Repository-development doc for GitHub Issue
[#415](https://github.com/amirbena/code-review-skill/issues/415), the
implementation issue
[`runtime-execution-contract.md`](../../runtime_platform/benchmark/runtime-execution-contract.md) §2.2/§8
scopes but does not itself implement. Like the rest of [`./`](../../runtime_platform/benchmark/README.md),
this is **not packaged into either Skill archive**, and no packaged Skill
resource depends on it.

This document fixes the concrete Claude Cloud Routine integration for
Class 2 (maintainer-controlled, optional quality observability —
`runtime-execution-contract.md` §2.2/§4.3). It does not redefine that
contract; a genuine contradiction discovered here is resolved by updating
`runtime-execution-contract.md`, not by silently deviating in this
document or in code.

> **Amended by [#467](https://github.com/amirbena/code-review-skill/issues/467)**
> (Epic [#466](https://github.com/amirbena/code-review-skill/issues/466); design
> record [#464](https://github.com/amirbena/code-review-skill/issues/464),
> [`scheduled-operations/`](../../runtime_platform/benchmark/scheduled-operations/README.md),
> amendments A1–A13 in
> [`contract-reconciliation.md`](../../runtime_platform/benchmark/scheduled-operations/contract-reconciliation.md)).
> Amended sections carry their IDs. Unchanged: the modes, positive completion
> verification, explicit metadata, non-reachability, and fail-closed behavior.
> `run_benchmark_routine.py` still implements the pre-amendment behavior
> (in-Routine `gh` posting) until the implementation issues of Epic #466 land,
> and those issues cite this text.

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
  → python3 runtime_platform/benchmark/scripts/run_benchmark_routine.py --mode <mode> ...
      → run_benchmark.py (unmodified §3 execution contract, once per case)
      → benchmark_routine_verify.verify_benchmark_output (positive
        completion check — never trusts the Routine's own "green" status)
      → on any unverified run: fail closed, exit non-zero, seal nothing
      → on a verified run: read the lane baseline (read-only), evaluate
        drift with in-run confirmation, and SEAL the canonical result
        to the handoff                                  ← commit point
──────────────── one-way publication boundary ────────────────
publication-only workflow (benchmark-publication App; no model, no
benchmark imports)
  → validate → persist the record on benchmark-history
  → post the evidence comment (§4) → reconcile drift issues
```

Order (A8): evaluate with in-run confirmation → seal → publish → issue
lifecycle. The Routine no longer posts evidence or pushes history itself (A2);
those are publication steps, and a sealed run whose publication fails is
republished from the seal, never re-run. How `smoke` and `selected` runs hand
off their output is fixed by the execution-entrypoint implementation issue;
neither has a GitHub write credential provisioned into it.

`run_benchmark_routine.py` (`runtime_platform/benchmark/scripts/run_benchmark_routine.py`)
is the only new execution-path code. It never re-implements
`run_benchmark.py`, the runner, the matcher, or the adapter — it shells
out to the existing `run_benchmark.py` CLI once per requested case id and
inspects its stdout.

### 2.1 Modes

Built on `run_benchmark.py`'s existing `--case-id` surface (§9 of
`runtime-execution-contract.md`'s parent contract; no new selection logic
is added here) plus, for `comprehensive`, programmatic corpus-membership
discovery added by #431
(`runtime_platform/benchmark/scripts/benchmark_corpus_membership.py`):

| Mode | Case ids | Use |
| --- | --- | --- |
| `smoke` | one or a few explicit `--case-id` values | sanity-check the Routine itself |
| `selected` | whatever `--case-id` list is handed to it (e.g. a future #334 Top-K output) | PR-time-adjacent observability, never a merge gate |
| `sentinel` | none — runs the whole `--corpus-dir` (non-recursive: the 4 permanent canonical cases) | scheduled sentinel lane, maximum gap ≤ 96 h (#431, A11) |
| `comprehensive` | none — runs every `benchmark-case/v2` fixture discovered recursively under `--corpus-dir` | scheduled comprehensive lane, maximum gap ≤ 8 d (#431, A11) |
| `full` | none — **deprecated fixed synonym for `sentinel`** (#431) | kept, unchanged in behavior, only for backward compatibility with existing Routine prompt configuration; emits a stderr deprecation notice; new configuration must use `sentinel` explicitly. Never means `comprehensive`. |
| `auth-check` | none — no benchmark run | handoff and publisher smoke test (§5) |

`sentinel` and `comprehensive` are the two-tier scheduled execution lanes
`docs/benchmark/corpus/README.md` and
`runtime_platform/benchmark/nightly-history-and-baseline.md` §2 define; `full`'s
pre-#431 ambiguity (it happened to only ever resolve to the 4 top-level
cases, because `--corpus-dir`'s glob is non-recursive) is resolved by this
table, not left as a second live meaning.

## 3. Positive completion verification

`runtime_platform/benchmark/scripts/benchmark_routine_verify.py::verify_benchmark_output`
is the fail-closed check. It never treats a non-zero exit, unparseable
stdout, a missing/malformed per-case result shape
(`runtime_platform/benchmark/runner-contract.md` §6), or any case whose `status` is
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

## 4. Evidence persistence (A1, A4)

The authoritative store for a scheduled run is a compact, content-hashed
**record on the isolated `benchmark-history` branch**, written by the
`benchmark-publication` App through the publication step — the store
[`nightly-history-and-baseline.md`](../../runtime_platform/benchmark/nightly-history-and-baseline.md)
§3 defines. This resolves the pre-amendment contradiction between that document
(a history branch) and this one (issue comments only). Evidence comments on a
maintainer-owned per-lane **tracking GitHub Issue** are the **human index and
notification**, never the store, and nothing is left in the Routine's own
transcript/run history:

- the record is durable and inspectable independent of Routine run retention
  (§2.2 of the runtime contract; undocumented Routine-side retention was the
  reason this document rejects relying on it);
- it is machine-readable and addressable by an immutable commit permalink, so
  [#338](https://github.com/amirbena/code-review-skill/issues/338) (history/baseline)
  and [#339](https://github.com/amirbena/code-review-skill/issues/339)
  (drift/issue lifecycle) read a baseline as a direct file read, not a paginated
  comment scrape;
- it is never reachable from contributor PR automation — the record and the
  tracking issue are written only by the publisher, and the tracking issues are
  locked to collaborators.

Each **evidence comment**, one per published run, begins with the per-run
marker `<!-- benchmark-run:<run_id> -->` (A4; it replaces the constant evidence
marker, so a retried post is skipped instead of appended), then a short human
summary — lane, repository SHA, model, executed/total cases, drift outcome,
baseline state — and two **immutable commit-pinned permalinks**, to the record
and to the baseline it was compared against, plus links to any issues acted on.
The runtime/model/SHA metadata set `runtime-execution-contract.md` §5 requires
lives in the record. The tracking-issue numbers are part of the repository-owned
schedule spec, and a Routine no longer passes an evidence-issue argument.

### Rejected: evidence committed to reviewed branches or Skill source

Pushing evidence JSON directly into `main`, a pull-request branch, or any other
reviewed branch or Skill source from an unattended run was considered and
rejected: it would bypass this repository's own PR-review workflow
([`../../policies/git-pr-merge-policy.md`](../../policies/git-pr-merge-policy.md))
for every scheduled run, which is a larger, harder-to-audit surface than the
alternatives. **This rejection is narrowed (A1)**: it does not cover the
isolated `benchmark-history` branch, which is neither a reviewed branch nor
Skill source — the argument
[`nightly-history-and-baseline.md`](../../runtime_platform/benchmark/nightly-history-and-baseline.md)
§3.1 already makes — and that branch is written by the publication App, not by
the Routine.

### Rejected: issue comments as the store

Editable by their author, length-capped by the API, unschematized, and paged
through to read a baseline — which is why they are the index, not the store.

## 5. Handoff and publisher smoke test (A2)

`--mode auth-check` is repurposed. It no longer proves GitHub issue
create/comment permissions from inside the Routine — no GitHub write credential
is provisioned there. It smoke-tests the **handoff** (a Routine can seal a
result) and the **publisher** (the publication step can read and validate it),
independent of any benchmark run, not `gh`. Run it once whenever the Routine's
connection or the App changes, and before the first scheduled run relies on
unattended publication; its exact behavior is fixed by the execution-entrypoint
implementation issue.

**Residual risk R1 is documented, not denied.** A Routine clones and pushes
through the maintainer's provider-side GitHub connection; its git credentials
stay outside the sandbox behind a proxy that authenticates with scoped
credentials, and its GitHub actions are attributed to the maintainer. This
repository cannot show what scope that proxy credential has. The seal is
confined by the provider to `claude/`-prefixed refs, and an observed check —
attempt a non-`claude/` push and an issue create from a Routine smoke run — is
recorded at provisioning rather than assumed
([`scheduled-operations/execution-publication-boundary.md`](../../runtime_platform/benchmark/scheduled-operations/execution-publication-boundary.md)
§4).

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

## 7. Credential / usage bounding (A2)

Execution keeps the maintainer's **Claude account** only: the Routine runs under
the maintainer's own already-authorized Claude Cloud Routine session. **No
GitHub write credential is provisioned into the runtime**, and repository-owned
execution code performs no GitHub mutation other than the seal — itself a
bounded, provider-mediated write (§5). All other GitHub writes are made by the
dedicated `benchmark-publication` GitHub App, whose short-lived installation
token is minted inside the publication-only workflow with per-phase minimum
permissions; it is independently revocable, distinct from the release App, and
never present on the execution side. This replaces the pre-amendment model, in
which execution ran under the maintainer's own `gh` identity and the Routine
posted evidence and pushed history itself.

The maintainer configuring a schedule remains responsible for sizing run
frequency and corpus scope against their Claude subscription usage and the
account's Routine run limits — this document does not fix a specific schedule,
only the vehicle a schedule invokes.

## 8. Non-reachability from contributor automation (A13)

The invariant is: **no GitHub Actions workflow schedules, runs, re-runs, or
evaluates the benchmark, and none is a contributor or merge prerequisite.**
Nothing on the execution side of this document's pipeline is invoked by
`.github/workflows/**` or any other repository-triggered automation — there is
no independent GitHub Actions benchmark execution path left over from the
retired #255 workflow (#420) for it to couple to. `run_benchmark_routine.py` is
dead code from the contributor-PR path's perspective — it is only ever invoked
by a maintainer-configured Cloud Routine prompt (§9) or by a maintainer running
it locally by hand. `runtime_platform/benchmark/selection.md`'s existing
non-blocking, informational-only contributor path (#334) is unchanged by this
document.

The blanket phrasing "no GitHub Actions cron", used in earlier documents, was
written about benchmark scheduling and execution. It does not forbid a
**publication-only workflow** — a `schedule` sweep and watchdog plus manual
`workflow_dispatch`, defined on the default branch, that reads sealed records,
holds no model or provider credential, imports nothing from the benchmark, and
judges nothing. That workflow is permitted and is a different thing; its
triggers, credentials, and imports are enforced by a policy test
([`scheduled-operations/publication-architecture.md`](../../runtime_platform/benchmark/scheduled-operations/publication-architecture.md)
§5).

## 9. Routine prompt template

The instructions a maintainer pastes into a Claude Cloud Routine's own
task/schedule definition (outside this repository — Cloud Routines are
configured through Claude's own product surface, not a repository file that
executes automatically) are a **thin prompt spec** (A12). The multi-step prompt
of the pre-amendment template — dependency installs, `gh` evidence posting, and
a history push — is replaced; all logic is repository code at the pinned SHA, so
provider-side prompt drift cannot change behavior:

```text
1. Check out a fresh copy of amirbena/code-review-skill at <ref, default main>.
2. Run:
   python3 runtime_platform/benchmark/scripts/run_benchmark_routine.py \
     --mode <sentinel|comprehensive|smoke|selected|auth-check> \
     [--case-id <id> ...] \
     --model-id <the model backend this Routine session is running as>
3. If the command exits non-zero, stop — do not report success, do not retry
   silently, and do not post or push anything to GitHub. A run that did not
   seal is not a verified run.
```

The tracking-issue numbers, cadence text, `max_gap_hours`, and confirmation
parameters are not Routine arguments: they live in the repository-owned
schedule spec.

### 9.1 Two lanes, two Cloud Routine schedules (#431)

The sentinel and comprehensive lanes (§2.1) are **two separate Cloud
Routine schedule configurations**, each pasting the template above with
its own `--mode` and its own recurrence, both targeting a **01:00
Israel-local start / 04:00 maximum-completion** window
(`runtime_platform/benchmark/nightly-history-and-baseline.md` §2). Timezone/DST
handling for that window is entirely a Cloud Routine scheduling-
configuration responsibility — set the schedule in Israel local time (or
in UTC with the correct seasonal offset) in the Routine's own product
surface; nothing in `runtime_platform/benchmark/scripts/` computes, stores, or adjusts for
a timezone.

| Lane | `--mode` | Maximum gap between verified scheduled runs |
| --- | --- | --- |
| Sentinel | `sentinel` | ≤ 96 h |
| Comprehensive | `comprehensive` | ≤ 8 d (192 h) |

Cadence is a **maximum gap**, not an exact interval; the weekday of the
comprehensive lane's 01:00 start is named explicitly, and the 04:00 window and
DST behavior are verified rather than assumed (A11 —
`nightly-history-and-baseline.md` §2).

**Collision is expected and never deduplicated.** The two schedules will
periodically land on the same night; when they do, both Routine runs execute,
verify, and are published independently — each with its own `run_id`, its own
per-lane tracking-issue thread, and its own keyed baseline
(`nightly-history-and-baseline.md` §4). This issue does not merge, skip, or
otherwise deduplicate a same-night collision.

## 10. Non-goals (restated from the parent Issue)

No drift-vs-noise policy, no regression fingerprinting, no GitHub issue
open/comment/close *lifecycle* (only a flat evidence-comment append), no
full-corpus baseline/history storage schema, no nightly scheduling
*policy* decision, no PR-time taxonomy/Top-K selection logic, and no
re-opening of Class 1 provisioning. All owned elsewhere per
`runtime-execution-contract.md` and the parent Issue's own Non-Goals
section.

## 11. Addendum: `--results-out` for nightly history (#338), amended by A2/A8

[#338](https://github.com/amirbena/code-review-skill/issues/338) added an
optional `--results-out PATH` flag to `run_benchmark_routine.py`: on a
verified run only, it writes the concatenated raw per-invocation
`run_benchmark.py` output to that path. Omitting it is unaffected — the flag
stays additive and changes none of the modes or verification above.

What changed is its role and its ordering. Before the amendment, `--results-out`
was written **before** the evidence post, and a failed post raised and exited
non-zero, so the documented history step (which the prompt skipped whenever the
run exited non-zero) never ran for a run that had already verified. Under the
amended order there is no in-run GitHub post at all: the run evaluates drift,
then **seals** the canonical result (the commit point), and history is written
by the publication step from the sealed result
([`nightly-history-and-baseline.md`](../../runtime_platform/benchmark/nightly-history-and-baseline.md)
§2–§3). `--results-out` is therefore a local output, not the hand-off to
persistence, and a publication failure never needs or causes a benchmark
re-run.
