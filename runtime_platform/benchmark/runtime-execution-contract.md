# Benchmark Runtime Execution Contract

Repository-development contract for GitHub Issue
[#330](https://github.com/amirbena/code-review-skill/issues/330), revised
by [#391](https://github.com/amirbena/code-review-skill/issues/391). It
establishes the **vendor-neutral runtime execution contract, viability
criteria, and required-metadata rule** that any benchmark-execution
runtime must satisfy, without picking a winner. It is the foundational,
sequential root of the benchmark/measurement architecture (parent
[#329](https://github.com/amirbena/code-review-skill/issues/329)).

Like the rest of [`./`](README.md), this is a **repository-development
doc: not packaged into either Skill archive**, and no packaged Skill
resource depends on it. It restates and generalizes the fuller
architectural treatment in
[`../../docs/benchmark-measurement-architecture/benchmark-measurement-architecture-model.md`](../../docs/benchmark-measurement-architecture/benchmark-measurement-architecture-model.md)
§4 at the level a benchmark-specific reader needs, and does not fork it —
a conflict between the two is resolved by updating that canonical design
document, not this one.

**Revision note (#391).** #330's original text specified a single
execution class: a dedicated, provisioned CI runtime, gated on
[#336](https://github.com/amirbena/code-review-skill/issues/336)'s
empirical candidate spike and
[#337](https://github.com/amirbena/code-review-skill/issues/337)'s
provisioning. #336's spike (and its own #366 follow-up, closed without
merging — see
[`runtime-candidate-decision.md`](runtime-candidate-decision.md)) showed
every screened provider-backed CI candidate is either fidelity-poor,
quota-constrained, or cost-risky enough that none has cleared this
contract's own viability bar. #391 does not reopen that empirical
evidence (kept as historical record, §6/§8 below) — it responds to it
architecturally, by splitting execution into two classes (§2) instead of
one, so the fourteen-issue tree downstream is no longer load-bearing on a
provisioned CI runtime that has not materialized and is not being further
pursued. #337 is superseded by this split, not deleted from the record —
see §6 and §8.

> **Amended by [#467](https://github.com/amirbena/code-review-skill/issues/467)**
> (Epic [#466](https://github.com/amirbena/code-review-skill/issues/466); design
> record [#464](https://github.com/amirbena/code-review-skill/issues/464),
> [`scheduled-operations/`](scheduled-operations/README.md), amendments A1–A13
> in [`contract-reconciliation.md`](scheduled-operations/contract-reconciliation.md)).
> §2.2 changes in four ways, each marked by its ID: execution keeps the
> maintainer's Claude account but no longer holds a GitHub write credential
> (**A2**); the scheduler choice becomes an admissibility test with Cloud
> Routines as the selected default (**A3**); the pipeline order becomes
> evaluate → seal → publish → issue lifecycle (**A8**); and the "no GitHub
> Actions" statement is restated as the invariant it always meant (**A13**).
> Class 1 (§2.1), the execution contract (§3), the viability criteria (§4.1,
> §4.2), the metadata rule (§5), and the historical candidate record (§6) are
> unchanged.

## 1. Scope

This document owns four things: the two execution classes and the
trust boundary each carries (§2), the execution contract and runtime
viability criteria a candidate runtime must meet (§3–§4), and the
metadata that must be recorded with every benchmark result so a result
change is attributable to a Skill change versus a runtime/model change
(§5). It does **not** implement any actual scheduled integration, evidence
persistence, drift confirmation, or GitHub issue publication for the
maintainer-controlled class — that is scoped to a future implementation
issue against §2.2's fixed pipeline, not this contract itself (see §8,
§9).

## 2. Two execution classes

Every prior version of this contract addressed one implicit class:
execution automatically triggered by repository activity (a PR, including
one from a fork), where the input reaching the runtime cannot be trusted.
That class still exists and keeps its original rule unchanged (§2.1). This
revision adds a second, architecturally distinct class: execution the
maintainer themselves initiates or schedules, where there is no untrusted
input in the path at all (§2.2). The two classes are not degrees of the
same trust boundary — they answer different questions, and a runtime
proposal must state which class it targets before being checked against
the rest of this document.

### 2.1 Class 1 — Automatic / repository-triggered execution (untrusted input)

Applies to any execution a repository-controlled workflow triggers
automatically — on a PR, a push, or any other repository event —
including a fork PR the maintainer did not author.

Benchmark execution in this class must **never** run on the maintainer's
personal workstation, credentials, filesystem, shell, SSH state, or
browser/session state — under any trigger, including a fork PR. This is a
trust-boundary requirement, not an availability optimization, and it is
not weighed against cost or fidelity: a candidate that cannot satisfy it
is disqualified regardless of how well it otherwise scores.

Execution in this class must run on infrastructure dedicated to CI, never
a device that doubles as anything else, using a purpose-specific,
minimally scoped, independently revocable credential, with fork-PR/
untrusted input kept separated from any secret-bearing execution path.

**Current status:** no candidate has cleared this class's viability bar
(§6, §8) at an acceptable cost (see
[`runtime-candidate-decision.md`](runtime-candidate-decision.md) §6-§8.4).
Provisioning work for this class (#337) is superseded — see §8. This
class's rule itself is unchanged and stays the reference for any future
proposal that does try to satisfy it; the fourteen-issue tree downstream
no longer depends on one existing (§2.3 of
[`../../docs/benchmark-measurement-architecture/benchmark-measurement-architecture-model.md`](../../docs/benchmark-measurement-architecture/benchmark-measurement-architecture-model.md)).

### 2.2 Class 2 — Maintainer-controlled execution (optional quality observability)

Applies only to execution the maintainer themselves initiates — an
on-demand run, or a schedule the maintainer configured — never triggered
by contributor PR automation, a fork PR, or any other repository event.
There is no untrusted input in this class's execution path: the maintainer
already trusts their own already-authorized credentials and identity for
every other kind of repository work they do, and this class does not
create a new attacker-reachable surface the way Class 1's automatic
triggers would.

This class is **optional maintainer quality observability, never a
contributor or merge prerequisite.** Concretely:

- It must never become reachable from contributor PR automation, and must
  never become a required check for a normal contributor PR or merge —
  [`selection.md`](selection.md)'s informational-only, non-blocking
  PR-time Top-K selection (#334) is the permanent, intended state for
  every contributor, not a temporary bootstrapping gap pending this class
  landing. There is no independent GitHub Actions benchmark execution
  path from the retired #255 workflow for this class to eventually
  replace.
- **The invariant (A13): no GitHub Actions workflow schedules, runs,
  re-runs, or evaluates the benchmark, and none is a contributor or merge
  prerequisite.** Earlier statements phrased as a blanket "no GitHub Actions
  cron" were written about benchmark scheduling and execution. A
  **publication-only workflow** — a `schedule` sweep and watchdog plus manual
  `workflow_dispatch`, defined on the default branch, that reads sealed
  records, holds no model or provider credential, imports nothing from the
  benchmark, and judges nothing — is permitted and is a different thing. Its
  triggers, credentials, and imports are enforced by a policy test
  ([`scheduled-operations/publication-architecture.md`](scheduled-operations/publication-architecture.md)
  §5).
- A maintainer who never configures any Class 2 execution still has a
  fully functional repository and contribution workflow — nothing in this
  class is load-bearing for ordinary repository use.
- **Execution (A2)** runs with the maintainer's own already-authorized
  **Claude account** — not a separately provisioned, repository-level,
  independently-revocable model credential the way Class 1 requires; there is
  no untrusted input in the path. It does **not** run under the maintainer's
  GitHub identity for writes: no GitHub write credential is provisioned into
  the runtime, and repository-owned execution code performs no GitHub
  mutation other than the seal (a bounded write mediated by the provider).
  GitHub writes are made by a dedicated, independently revocable
  `benchmark-publication` GitHub App whose short-lived token is minted inside
  the publication-only workflow, never on the execution side. The residual
  risk that a Routine's provider-native GitHub identity is attributed to the
  maintainer is recorded, not denied
  ([`scheduled-operations/execution-publication-boundary.md`](scheduled-operations/execution-publication-boundary.md)
  §4, residual R1).

**Selected scheduled-integration target: Claude Cloud Routines (A3).**
Cloud Routines are the selected default; the choice is now an **admissibility
test** rather than a closed list. A scheduler is admissible only if it is
maintainer-controlled; not triggered by repository events; independent of a
personal machine being on; runs the unchanged entrypoint; and has no
provisioned GitHub write credential. Cloud Routines meet it. Claude Desktop
scheduled tasks stay explicitly excluded, and so does GitHub Actions as a
*benchmark* scheduler or runner (§7; A13 says what Actions may do). The
recommended architecture needs no other scheduler — admitting one is
optional. Desktop scheduled tasks fail the test: they require the
maintainer's own machine to be on and the desktop application open to fire,
which is structurally the same
personal-machine/personal-session dependency §2.1 forbids for Class 1,
even though Class 2's threat model is different (no untrusted input, so
it does not violate §2.1's *rule* — but it reintroduces the *availability*
failure mode this project's benchmark architecture has otherwise avoided,
and is asymmetric with Class 2's own goal of *reliable* periodic
observability). Cloud Routines run independent of any specific machine
being on or awake, which is why they are the selected target.

**Two scheduled lanes (#431).** The concrete Routine integration below
(#338/#415, later refined into two lanes by #431 —
[`cloud-routine-integration.md`](../../docs/benchmark/cloud-routine-integration.md) §2.1,
[`nightly-history-and-baseline.md`](nightly-history-and-baseline.md) §2)
runs as **two** maintainer-configured Cloud Routine schedules, not one: a
**sentinel** lane (the 4 permanent canonical cases, maximum gap ≤ 96 h) and a
**comprehensive** lane (every `benchmark-case/v2` fixture in the corpus
tree, maximum gap ≤ 8 d). Cadence is a maximum gap, not an exact interval
(A11; `nightly-history-and-baseline.md` §2). Both stay within this section's Class 2 boundary — optional
maintainer quality observability, never a contributor/PR/merge/deployment
requirement, targeting a 01:00 Israel-local start / 04:00 maximum-
completion window that Cloud Routine scheduling configuration owns (never
repository runtime logic — nothing in `runtime_platform/benchmark/scripts/` computes or
depends on a timezone). A future implementation issue (scoped separately,
not by this contract) owns the concrete Routine integration, fixed to this
pipeline (order amended by A8 — evaluation, with in-run confirmation, now
precedes the seal and all GitHub writes; the pre-amendment order was persist
→ evaluate → issues):

```text
benchmark measurement core (scheduler-independent, unchanged — §3):
  corpus → runner → ReviewerAdapter → matcher/scoring → evidence/regression

scheduled benchmark integration (admissible-scheduler-specific, not yet built):
  Claude Cloud Routine
    → fresh repository checkout
    → explicitly pin/record evaluated SHA
    → invoke canonical benchmark pipeline (the core above, unmodified)
    → positively verify benchmark completion
    → evaluate drift, with in-run confirmation
    → seal the canonical result to a durable handoff      (commit point)
  ─────────────── one-way publication boundary ───────────────
  publication-only workflow (benchmark-publication App)
    → persist durable evidence
    → bounded GitHub issue lifecycle (from the sealed result's confirmed drift)
```

That implementation issue must additionally satisfy, at minimum: never
trust a Routine's "green" run status as proof the benchmark succeeded (a
green run only means the session exited without an infrastructure error);
positively verify the benchmark produced the runner's stable per-case
result shape before treating a run as evidence; record repository SHA and
runtime/model metadata (§5) with every persisted result, since neither is
automatic; never rely on the Routine's own transcript/run-history as the
durable benchmark store; empirically verify the handoff and the publisher —
and the observed scope of the provider-native identity (R1) — before relying
on unattended operation; publish from the sealed result only, so a
publication failure never requires a benchmark re-run; and account for the
maintainer's Claude subscription usage and the account's Routine run limits
when sizing any scheduled run.

## 3. Execution contract

Shared by both classes (§2) — vendor-neutral, and the same regardless of
who or what triggers execution:

```text
run_benchmark.py
  → ReviewerAdapter (runtime_platform/benchmark/scripts/benchmark_review_adapter.py —
      resolve_cli_executable, BENCHMARK_REVIEW_CLI[_ARGS],
      check_runtime_available, RuntimeUnavailableError)
    → compatible agent CLI/runtime      (candidate-specific, swappable)
      → actual Skill (local-code-review, unmodified, unforked)
        → model backend                (candidate-specific, swappable)
```

A runtime that needs the Skill re-described in a different prompt/agent
format to run is disqualified — that would become a second, unofficial
reviewer implementation that can silently drift from the packaged source.
`ReviewerAdapter` stays a thin adapter around an unmodified
`SKILL.md`/`policies/`/`shared/`, never a translation layer that
reimplements the Skill's semantics.

## 4. Runtime viability criteria

### 4.1 Core criteria (both classes)

A candidate runtime, in either class, must reliably:

- inspect the repository like a real developer checkout;
- execute the Skill's required tools non-interactively;
- invoke the Skill's actual semantics with minimal-to-no translation;
- run non-interactively;
- normalize its output through a thin `ReviewerAdapter`;
- prefer free / near-zero cost **without** sacrificing fidelity — a
  cheaper candidate that cannot actually invoke the Skill's real
  multi-step, tool-using semantics is not viable regardless of cost;
- stay reproducible: runtime/model version pinned and recorded (§5);
- never render a `runtime-unavailable` outcome as a silent green gate —
  it must stay a distinct, visible, non-passing state (as
  [`selection.md`](selection.md)'s explicit `insufficient-coverage` and
  runtime-unavailable outcomes already do for today's PR-time path, and as
  §2.2's future Routine integration must for the maintainer-controlled
  class);
- stay swappable behind the `ReviewerAdapter` boundary, so changing
  providers later never requires touching the runner, matcher, metrics,
  selector, or nightly pipeline.

### 4.2 Additional criteria — Class 1 (automatic / repository-triggered)

- fit a bounded PR-check latency budget;
- run on CI-dedicated infrastructure never used for anything else;
- carry no dependency on the maintainer's personal machine (§2.1);
- keep fork-PR/untrusted input separated from any secret-bearing path;
- use a purpose-specific, independently revocable credential.

### 4.3 Additional criteria — Class 2 (maintainer-controlled)

- never reachable from contributor PR automation, and never a required
  check for a normal contributor PR or merge (§2.2);
- for the scheduled-integration case specifically: an admissible scheduler
  (§2.2, A3) — Claude Cloud Routines are the selected default — never Claude
  Desktop scheduled tasks, and never GitHub Actions as a benchmark scheduler
  or runner;
- positively verify benchmark completion rather than trusting a
  scheduler's own run status as proof of success (§2.2);
- persist evidence durably outside the scheduler's own transcript/run
  history (§2.2), by publication from a sealed result rather than by a
  GitHub write from the runtime (A2).

## 5. Runtime metadata required with every result

Every benchmark result must carry, at minimum:

- runtime/CLI name and version;
- model/backend identifier and version/tag, where exposed;
- the Skill/repository SHA the review ran against.

This lets every consumer of a benchmark result attribute a result change
to a Skill change versus a runtime/model change, rather than having the
two silently confounded. Wiring this into `run_benchmark.py`'s output is
implementation work for whichever issue provisions a runtime in either
class — a future Class 1 proposal, or the Class 2 Routine-integration
issue (§2.2) — not a contract this document implements itself.

## 6. Candidate classes (Class 1, historical)

Evaluated against §4.1/§4.2; scoped to Class 1 (automatic/repository-
triggered execution) only — Class 2's runtime is simply the maintainer's
own already-authorized Claude session or Cloud Routine (§2.2), which does
not need a separate candidate evaluation the way a shared, repository-
level CI credential did. This table is **historical record, not an open
decision**: #336's empirical spike (and its #366 follow-up) already ran
class A and a class-B candidate, and neither cleared this contract's bar
at an acceptable cost — see
[`runtime-candidate-decision.md`](runtime-candidate-decision.md). No
further Class 1 candidate evaluation is being pursued (§8); this table is
kept so a future revisit of Class 1 is not forced to re-derive it.

| Class | Description | Verdict |
| --- | --- | --- |
| A — Claude Code CLI + Anthropic backend, dedicated CI credential | Reference runtime the Skill/corpus were calibrated against; no translation layer. | Highest fidelity and lowest operational maintenance; metered but small, bounded cost. Safe fallback if no other class clears fidelity. |
| B — another proven agent CLI with an existing Ollama/open-model integration | Points the candidate runtime at the packaged Skill resources unmodified. | $0 backend; fidelity and CPU-latency unproven without #336's spike. Not pre-rejected. |
| C — another free/near-zero-cost hosted agent-capable runtime | A hosted, tool-use-capable surface, not a bare completion endpoint (disqualified — see §7). | Evaluate case-by-case in the spike; no specific provider named here. |
| D — dedicated isolated remote/self-hosted runner | Infrastructure layer hosting any of A/B/C; only viable if genuinely dedicated, never doubling as a personal device. | Use only if the selected runtime doesn't fit a plain GitHub-hosted runner. |

## 7. Rejected approaches

Documented so none is silently re-proposed. All are rejected on
architectural grounds, not vendor identity.

**Class 1 (automatic/repository-triggered):**

- **A self-hosted runner reusing the maintainer's personal authenticated
  session.** This creates exactly the forbidden personal-machine path
  (§2.1), regardless of which vendor's CLI or model it would run.
- **A bare single-shot completion endpoint standing in for the Skill.**
  It cannot run the Skill's real multi-step, tool-using loop without a
  second, unofficial reviewer implementation — the same disqualification
  as §3's re-described-Skill rule.

**Class 2 (maintainer-controlled):**

- **Claude Desktop scheduled tasks as the scheduled-integration
  mechanism.** Rejected specifically because reliable periodic benchmark
  monitoring must not depend on the maintainer's workstation being awake
  or the desktop application remaining open (§2.2) — not because Class
  2's trust boundary forbids the maintainer's own session (it doesn't;
  that is the whole point of Class 2), but because this mechanism
  reintroduces an availability dependency the architecture otherwise
  avoids.
- **GitHub Actions as a benchmark scheduler or runner (A3, A13).** Rejected
  because it would need a provider credential in a repository-hosted,
  contributor-adjacent runtime — the Class 1 shape whose candidates failed
  the viability bar (§2.1, §8). This is distinct from a publication-only
  workflow, which is permitted (§2.2).

## 8. Follow-up and current status

[#336](https://github.com/amirbena/code-review-skill/issues/336)'s
empirical spike (and its #366 follow-up) already ran the bounded
comparison §6 called for; neither Class 1 candidate cleared this
contract's bar at an acceptable cost — see
[`runtime-candidate-decision.md`](runtime-candidate-decision.md). No
further Class 1 candidate evaluation is being pursued.
[#337](https://github.com/amirbena/code-review-skill/issues/337), Class
1's provisioning issue, is **superseded** by this revision: it is no
longer load-bearing for any downstream benchmark-architecture work (see
[`../../docs/benchmark-measurement-architecture/benchmark-measurement-architecture-model.md`](../../docs/benchmark-measurement-architecture/benchmark-measurement-architecture-model.md)
§2), and should be closed pointing back to
[#391](https://github.com/amirbena/code-review-skill/issues/391).

For Class 2, this document fixes the contract (§2.2, §4.3) but does not
implement it: the concrete Claude Cloud Routine integration — profiles,
Routine execution, drift confirmation, evidence persistence, GitHub issue
publication — is implemented against §2.2's pipeline by the implementation
issues of Epic
[#466](https://github.com/amirbena/code-review-skill/issues/466), not by this
document.

## 9. Out of scope

- Picking a Class 1 runtime/provider, or re-evaluating #336/#366's
  already-run candidates.
- Standing up any actual infrastructure, credential, or workflow for
  either class — including the Class 2 Routine integration itself
  (profiles, Routine execution, drift confirmation, evidence persistence,
  GitHub issue publication). Scoped to the implementation issues of Epic
  #466 against §2.2, not this contract.
- Any change to the corpus, runner, matcher, or metrics
  ([#52](https://github.com/amirbena/code-review-skill/issues/52)/[#53](https://github.com/amirbena/code-review-skill/issues/53)/[#54](https://github.com/amirbena/code-review-skill/issues/54)/[#55](https://github.com/amirbena/code-review-skill/issues/55)/[#56](https://github.com/amirbena/code-review-skill/issues/56)/[#57](https://github.com/amirbena/code-review-skill/issues/57)) —
  confirmed already environment-agnostic, untouched by this revision.
- Broadly rewriting the applicability classifier or Top-K selection
  ([#331](https://github.com/amirbena/code-review-skill/issues/331)) or
  nightly scheduling
  ([#332](https://github.com/amirbena/code-review-skill/issues/332)) —
  see the canonical design doc's follow-up-corrections note for the
  bounded wording corrections those issues (and #335/#338/#339) will need
  in separate, later changes.

## Related

The PR-level CI check #255 introduced
(`.github/workflows/benchmark-check.yml`,
`runtime_platform/benchmark/scripts/benchmark_ci_classifier.py`) has been retired
([#420](https://github.com/amirbena/code-review-skill/issues/420)):
[`selection.md`](selection.md) (#334, over #333's taxonomy/index) is now
the contributor-facing, non-blocking PR-time path, and its
informational-only, never-a-merge-prerequisite behavior is the
**permanent** state (§2.2), not a gap this contract's Class 1 runtime was
meant to eventually fill. The fuller cross-component
architecture — the canonical dependency DAG, the nine architecture layers,
and how this contract's §3–§5 fits the PR and nightly benchmark paths — is
[`../../docs/benchmark-measurement-architecture/benchmark-measurement-architecture-model.md`](../../docs/benchmark-measurement-architecture/benchmark-measurement-architecture-model.md)
§4.
