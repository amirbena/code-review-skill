# Benchmark CI Runtime Execution Contract

Repository-development contract for GitHub Issue
[#330](https://github.com/amirbena/code-review-skill/issues/330). It
establishes the **vendor-neutral runtime execution contract, viability
criteria, and required-metadata rule** that any future benchmark-execution
CI runtime must satisfy, without picking a winner. It is the foundational,
sequential root of the benchmark/measurement architecture (parent
[#329](https://github.com/amirbena/code-review-skill/issues/329)):
[`ci-integration.md`](ci-integration.md) §4 already documents that
`scripts/benchmark/run_benchmark.py` / `benchmark_review_adapter.py` have
no working runtime on a bare Actions runner today — this document is the
contract a runtime proposal that fills that gap must be checked against.

Like the rest of [`./`](README.md), this is a **repository-development
doc: not packaged into either Skill archive**, and no packaged Skill
resource depends on it. It restates and generalizes the fuller
architectural treatment in
[`../benchmark-measurement-architecture/benchmark-measurement-architecture-model.md`](../benchmark-measurement-architecture/benchmark-measurement-architecture-model.md)
§4 at the level a benchmark-specific reader needs, and does not fork it —
a conflict between the two is resolved by updating that canonical design
document, not this one.

## 1. Scope

This document owns three things: the non-negotiable trust boundary, the
execution contract and runtime viability criteria a candidate runtime must
meet, and the metadata that must be recorded with every benchmark result
so a result change is attributable to a Skill change versus a
runtime/model change. It does **not** pick the final runtime or provider
(that is [#336](https://github.com/amirbena/code-review-skill/issues/336)'s
empirical spike), and it does not provision any actual infrastructure,
credential, or workflow (that is
[#337](https://github.com/amirbena/code-review-skill/issues/337), which
depends on #336's decision record).

## 2. Non-negotiable trust boundary

Benchmark CI must **never** execute on the maintainer's personal
workstation, credentials, filesystem, shell, SSH state, or browser/session
state — under any trigger, including a fork PR the maintainer did not
author. This is a trust-boundary requirement, not an availability
optimization, and it is not weighed against cost or fidelity: a candidate
that cannot satisfy it is disqualified regardless of how well it otherwise
scores.

Execution must run on infrastructure dedicated to CI, never a device
that doubles as anything else, using a purpose-specific, minimally scoped,
independently revocable credential, with fork-PR/untrusted input kept
separated from any secret-bearing execution path.

## 3. Execution contract

```text
run_benchmark.py
  → ReviewerAdapter (scripts/benchmark/benchmark_review_adapter.py —
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

A candidate runtime must reliably:

- inspect the repository like a real developer checkout;
- execute the Skill's required tools non-interactively;
- invoke the Skill's actual semantics with minimal-to-no translation;
- run non-interactively in isolated CI;
- normalize its output through a thin `ReviewerAdapter`;
- prefer free / near-zero cost **without** sacrificing fidelity — a
  cheaper candidate that cannot actually invoke the Skill's real
  multi-step, tool-using semantics is not viable regardless of cost;
- stay reproducible: runtime/model version pinned and recorded (§5);
- fit a bounded PR-check latency budget;
- run on CI-dedicated infrastructure never used for anything else;
- carry no dependency on the maintainer's personal machine (§2);
- keep fork-PR/untrusted input separated from any secret-bearing path;
- use a purpose-specific, independently revocable credential;
- never render a `runtime-unavailable` outcome as a silent green gate —
  it must stay a distinct, visible, non-passing state (as
  [`ci-integration.md`](ci-integration.md) §4 already does for today's
  no-runtime-configured case);
- stay swappable behind the `ReviewerAdapter` boundary, so changing
  providers later never requires touching the runner, matcher, metrics,
  selector, or nightly pipeline.

## 5. Runtime metadata required with every result

Every benchmark result must carry, at minimum:

- runtime/CLI name and version;
- model/backend identifier and version/tag, where exposed;
- the Skill/repository SHA the review ran against.

This lets every consumer of a benchmark result attribute a result change
to a Skill change versus a runtime/model change, rather than having the
two silently confounded. Wiring this into `run_benchmark.py`'s output is
implementation work for whichever issue provisions the selected runtime
(#337), not a contract this document implements itself.

## 6. Candidate classes

Evaluated against §4 above; this is **not a decision** — #336's empirical
spike decides among them.

| Class | Description | Verdict |
| --- | --- | --- |
| A — Claude Code CLI + Anthropic backend, dedicated CI credential | Reference runtime the Skill/corpus were calibrated against; no translation layer. | Highest fidelity and lowest operational maintenance; metered but small, bounded cost. Safe fallback if no other class clears fidelity. |
| B — another proven agent CLI with an existing Ollama/open-model integration | Points the candidate runtime at the packaged Skill resources unmodified. | $0 backend; fidelity and CPU-latency unproven without #336's spike. Not pre-rejected. |
| C — another free/near-zero-cost hosted agent-capable runtime | A hosted, tool-use-capable surface, not a bare completion endpoint (disqualified — see §7). | Evaluate case-by-case in the spike; no specific provider named here. |
| D — dedicated isolated remote/self-hosted runner | Infrastructure layer hosting any of A/B/C; only viable if genuinely dedicated, never doubling as a personal device. | Use only if the selected runtime doesn't fit a plain GitHub-hosted runner. |

## 7. Rejected candidates

Documented so neither is silently re-proposed. Both are rejected on
architectural grounds, not vendor identity:

- **A self-hosted runner reusing the maintainer's personal authenticated
  session.** This creates exactly the forbidden personal-machine path
  (§2), regardless of which vendor's CLI or model it would run.
- **A bare single-shot completion endpoint standing in for the Skill.**
  It cannot run the Skill's real multi-step, tool-using loop without a
  second, unofficial reviewer implementation — the same disqualification
  as §3's re-described-Skill rule.

## 8. Follow-up

[#336](https://github.com/amirbena/code-review-skill/issues/336) is the
bounded empirical spike this contract requires before a runtime is
selected: run the same benchmark case(s) through the strongest viable
candidates from §6 and compare fidelity, latency, and operational
complexity, ending in a decision record rather than open-ended
exploration.
[#337](https://github.com/amirbena/code-review-skill/issues/337)
provisions whatever #336 selects, including wiring the §5 metadata into
`run_benchmark.py`'s output.

## 9. Out of scope

- Picking the final runtime/provider (#336).
- Standing up any actual infrastructure, credential, or workflow (#337).
- Any change to the corpus, runner, matcher, or metrics
  ([#52](https://github.com/amirbena/code-review-skill/issues/52)/[#53](https://github.com/amirbena/code-review-skill/issues/53)/[#54](https://github.com/amirbena/code-review-skill/issues/54)/[#55](https://github.com/amirbena/code-review-skill/issues/55)/[#56](https://github.com/amirbena/code-review-skill/issues/56)/[#57](https://github.com/amirbena/code-review-skill/issues/57)),
  the applicability classifier or Top-K selection
  ([#331](https://github.com/amirbena/code-review-skill/issues/331)), or
  nightly scheduling
  ([#332](https://github.com/amirbena/code-review-skill/issues/332)).

## Related

[`ci-integration.md`](ci-integration.md) (#255) is the existing PR-level
CI check that this contract's eventual runtime fills the
"applicable, runtime unavailable" gap for. The fuller cross-component
architecture — the canonical dependency DAG, the nine architecture layers,
and how this contract's §3–§5 fits the PR and nightly benchmark paths — is
[`../benchmark-measurement-architecture/benchmark-measurement-architecture-model.md`](../benchmark-measurement-architecture/benchmark-measurement-architecture-model.md)
§4.
