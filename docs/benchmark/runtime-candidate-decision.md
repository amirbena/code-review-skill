# Benchmark CI Runtime Candidate Decision Record

Repository-development decision record for GitHub Issue
[#336](https://github.com/amirbena/code-review-skill/issues/336), the
bounded empirical spike
[`runtime-execution-contract.md`](runtime-execution-contract.md) (#330)
requires before a runtime is selected. It records the actual candidates
run, the evidence gathered, and the resulting recommendation for
[#337](https://github.com/amirbena/code-review-skill/issues/337)
(provisioning) — it does not re-derive #330's contract or viability
criteria, only applies them.

Like the rest of [`./`](README.md), this is a **repository-development
doc: not packaged into either Skill archive**, and no packaged Skill
resource depends on it.

## 1. Scope of this spike

Per #336 and #330 §8, this is a small, time-boxed comparison — not a
tuning exercise and not a re-run of the full corpus. Two corpus cases were
run through each candidate:

- [`correctness-off-by-one-pagination`](corpus/correctness-off-by-one-pagination.yaml)
  — a finding-expected case (one required P1 finding).
- [`no-op-comment-and-rename`](corpus/no-op-comment-and-rename.yaml) — the
  corpus's one clean/no-findings case.

Both candidates below were pointed at this checkout's unmodified
`skills/local-code-review/`, `policies/`, and `shared/` resources through a
thin, throwaway `ReviewerAdapter` (per #330 §3 and #336's scope, neither
adapter is committed to the repository — this document inlines the
evidence instead). Runtime/model/Skill-SHA metadata (#330 §5): Skill/repo
SHA `3c5f783` (`main`), spike run date 2026-09-15.

## 2. Candidates run

| Candidate | Class (§6 of #330) | Runtime | Model/backend |
| --- | --- | --- | --- |
| A | A | `claude` CLI 2.1.272 | Anthropic backend, default model configured for the CLI in this environment |
| B | B | `opencode` CLI 1.18.15 | local Ollama `qwen3-coder:latest` (18 GB, `@ai-sdk/openai-compatible` provider against `http://localhost:11434/v1`) |

No class-C candidate (a free/near-zero-cost hosted agent-capable runtime)
was available or credentialed in this environment, so class C was **not
evaluated** — recorded as such rather than rejected. No class-D candidate
applies: this spike deliberately ran on a local development machine (never
a CI provisioning decision, and never the personal-machine CI path §2 of
#330 forbids — that trust boundary governs where the *selected* runtime
executes in CI, not where this throwaway spike was run).

## 3. Method

For each candidate, a thin adapter was built that:

1. materializes the case's `base` + `patch` into an isolated Git
   workspace (the same materialization the existing
   [`runner-contract.md`](runner-contract.md) uses);
2. invokes the candidate CLI non-interactively, pointed at the
   unmodified Skill resources, with a prompt asking it to follow
   `skills/local-code-review/SKILL.md` and report in the same canonical
   finding-rendering format the production adapter already requires
   (`scripts/benchmark/benchmark_review_adapter.py`'s `_REVIEW_PROMPT`);
3. parses the CLI's final text output with the existing, unmodified
   `parse_review_output` — no candidate-specific parsing logic.

Candidate A reused the existing, already-packaged
`ProductionReviewerAdapter` unchanged. Candidate B's adapter copied
`skills/`, `policies/`, and `shared/` verbatim into the workspace (since
`opencode` has no equivalent of Claude Code's `--plugin-dir`) and pointed
`opencode run` at the same prompt and workspace.

## 4. Results

### Candidate A — `claude` CLI + Anthropic backend

| Case | Result | Latency |
| --- | --- | --- |
| `correctness-off-by-one-pagination` | Found the off-by-one at the correct location (`app/pagination.py`, the `page` function) with a correct claim describing the duplicated-row defect. Reported `P0`; the fixture permits `P1`/`P2` — an over-severity call on `severity-accuracy.md`'s ordinal, not a miss. | 26.1s |
| `no-op-comment-and-rename` | Correctly returned a clean report with no findings. | 34.9s |

Both cases executed on the first attempt, with no adapter/parse errors.
Both latencies sit well inside any plausible bounded PR-check budget.

### Candidate B — `opencode` CLI + local Ollama `qwen3-coder:latest`

| Case | Result | Latency |
| --- | --- | --- |
| `correctness-off-by-one-pagination` | No parseable review report. The model's final output stated it was trying to invoke an `explore` tool/agent, then a `general` agent, neither of which exists in this `opencode` installation (`opencode agent list` shows only `build`) — it never reached the point of reading the copied `SKILL.md` or the workspace diff. | 26.2s (to a non-review answer) |
| `no-op-comment-and-rename` | Same failure mode: repeated attempts to call `explore`/`general` agents, ending in an offer to help once the user specifies a task, and no review report. | 19.6s (to a non-review answer) |

Both runs raised `reviewer-adapter-raised` (unparseable output) under the
existing runner semantics — the same per-case error category the
production adapter already uses for a CLI that didn't produce a report.

To rule out that this was simply a missing-flag mistake in the throwaway
adapter (the default run above did not pin `--agent`), a follow-up attempt
re-ran the `correctness-off-by-one-pagination` case with the primary
agent pinned explicitly (`--agent build`). That single-case retry **did
not complete within 11 minutes** and was stopped — roughly 20x the latency
either case took under candidate A, and far outside any workable
PR-check latency budget regardless of the outcome it would eventually have
produced. Per #336's explicit time-box ("a spike, not an open-ended
research track"), no further OpenCode/Ollama configuration tuning was
attempted after this point.

## 5. Scored against #330 §4's viability criteria

| Criterion | Candidate A | Candidate B |
| --- | --- | --- |
| Inspect the repo like a real checkout | Met (both cases) | Not demonstrated — never reached the diff |
| Execute the Skill's required tools non-interactively | Met | Failed — stuck on non-existent tool/agent names before any Skill-directed tool use |
| Invoke the Skill's actual semantics with minimal-to-no translation | Met | Failed — no evidence the Skill content was ever read |
| Run non-interactively in isolated CI | Met | Launches non-interactively, but did not finish |
| Normalize output through a thin `ReviewerAdapter` | Met | N/A — no output to normalize |
| Prefer free/near-zero cost without sacrificing fidelity | Small, bounded Anthropic cost | $0 backend, but the contract is explicit that a cheaper candidate that cannot invoke the Skill's real semantics is not viable regardless of cost |
| Reproducible, version-pinned | Met (`claude` 2.1.272) | Met in the sense that the failure itself was reproducible across both cases and the retry |
| Bounded PR-check latency | Met (26–35s/case) | Failed (>11 min for one case, retry killed) |
| CI-dedicated infra / no personal-machine dependency | Applies to #337's provisioning, not this local spike | Same |
| Swappable behind `ReviewerAdapter` | Met structurally | Moot given the above |

Candidate B fails the two criteria the contract treats as
non-negotiable trade-offs against cost: it did not invoke the Skill's
actual multi-step, tool-using semantics, and it did not fit a bounded
PR-check latency budget, in either its default or explicit-agent
configuration tested here.

## 6. Decision

**Recommendation: provision class A (the Claude Code CLI against the
Anthropic backend, on a dedicated CI credential) for #337.**

- Candidate A cleared every #330 §4 criterion this spike could test
  empirically, at a small, bounded per-case cost and latency, using the
  existing, already-packaged `ProductionReviewerAdapter` unchanged.
- Candidate B (the one currently-real class-B/C candidate available in
  this environment — `opencode` + a local Ollama coding model) did not
  clear fidelity or latency in either configuration tested, and is
  recorded as **not viable in its current configuration** rather than
  worked around further, per #336's time-box.
- No class-C candidate was available to test empirically in this
  environment; class C is recorded as **not evaluated**, not rejected. A
  future spike may reopen class B/C with a different CLI, a different
  local/hosted model, or explicit agent-routing configuration — that is
  new work, not a re-run of this spike, and does not block #337.

This matches #330 §6's own assessment of class A as "the safe fallback if
no other class clears fidelity" — that is the outcome this spike's
evidence actually produced.

## 7. Known gap surfaced by this spike

Neither `ProductionReviewerAdapter` nor `run_benchmark.py` currently
records the model/backend identifier its `claude` CLI invocation actually
used (#330 §5's second metadata bullet) — only the CLI name/version is
observable today. This spike could only report "the default model
configured for the CLI in this environment" for candidate A. Wiring the
actual model identifier into `run_benchmark.py`'s output is provisioning
work for #337, which already owns wiring the full §5 metadata rule in
(per [`runtime-execution-contract.md`](runtime-execution-contract.md) §5);
this is not a new requirement, just a concrete gap #337 should close.

## 8. Out of scope

- Re-running the full corpus (#336 non-goal; a small, fixed subset is
  sufficient).
- Building a production-quality adapter for candidate B, or any further
  OpenCode/Ollama tuning (#336 non-goal and explicit time-box).
- Provisioning any real, persistent CI infrastructure, credential, or
  workflow (#337's scope).
- Deciding #331's Top-K selection logic or #332's nightly scheduling.

## Related

- [`runtime-execution-contract.md`](runtime-execution-contract.md) (#330)
  — the contract and viability criteria this decision applies.
- [`match-criteria.md`](match-criteria.md) / [`severity-accuracy.md`](severity-accuracy.md)
  — the existing metrics used to score candidate A's fidelity; no new
  metric was introduced.
- [#337](https://github.com/amirbena/code-review-skill/issues/337) —
  provisioning, which implements this decision record's recommendation.
