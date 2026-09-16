# Benchmark CI Runtime Candidate Decision Record

Repository-development decision record for GitHub Issue
[#336](https://github.com/amirbena/code-review-skill/issues/336), the
bounded empirical spike
[`runtime-execution-contract.md`](runtime-execution-contract.md) (#330)
requires before a runtime is selected. It records the actual candidates
run, the evidence gathered, and the resulting recommendation for
[#337](https://github.com/amirbena/code-review-skill/issues/337)
(provisioning) — it does not re-derive #330's contract or viability
criteria, only applies them, plus one added dimension #330 did not weigh
explicitly: this project's own economic sustainability (§6).

This project is an open-source side project with uncertain long-term
maintenance. A runtime candidate is not viable here merely because it
clears fidelity and latency — it must also be affordable indefinitely,
including by a maintainer who may stop actively maintaining the project.
§6 makes that constraint explicit and reframes §7's decision accordingly;
§4's empirical results and §5's fidelity/latency scoring are unchanged
from the original spike run and are not reopened by this addition.

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
| Prefer free/near-zero cost without sacrificing fidelity | Metered Anthropic usage; per-case cost was small in this 2-case spike, but §6 covers whether it stays bounded at realistic repository-scale usage | $0 backend, but the contract is explicit that a cheaper candidate that cannot invoke the Skill's real semantics is not viable regardless of cost |
| Reproducible, version-pinned | Met (`claude` 2.1.272) | Met in the sense that the failure itself was reproducible across both cases and the retry |
| Bounded PR-check latency | Met (26–35s/case) | Failed (>11 min for one case, retry killed) |
| CI-dedicated infra / no personal-machine dependency | Applies to #337's provisioning, not this local spike | Same |
| Swappable behind `ReviewerAdapter` | Met structurally | Moot given the above |

Candidate B fails the two criteria the contract treats as
non-negotiable trade-offs against cost: it did not invoke the Skill's
actual multi-step, tool-using semantics, and it did not fit a bounded
PR-check latency budget, in either its default or explicit-agent
configuration tested here.

## 6. Economic sustainability constraint (added to #336's scope)

#330 §4 already says a runtime should "prefer free / near-zero cost
without sacrificing fidelity," but does not put a number on it or say
what "cost" must actually be measured against. Because this is an
open-source side project with uncertain long-term maintenance, #336 was
amended to make that concrete rather than leaving "cost" a soft
preference a fidelity win could silently override:

- **$0 recurring cost is strongly preferred.** A metered backend is
  acceptable only if normal and burst usage can be bounded by a credible
  monthly ceiling — not merely "small in this 2-case spike."
- **The maintainer's absolute tolerance is approximately $40–50/month
  maximum**, but lower — ideally zero — recurring cost is preferred
  precisely because the project may not be actively maintained
  indefinitely: nobody may be watching a bill that quietly grows.
- **Any candidate with plausible triple-digit monthly spend under normal
  repository activity is not viable**, regardless of fidelity.
- A cost evaluation must account for the realistic drivers of spend, not
  just one PR-check invocation:
  - PR-time selected benchmark cases (whatever subset #331 selects, not
    just this spike's 2 cases);
  - reruns and push churn on the same PR;
  - concurrent PR activity across the repository;
  - the future nightly/full-corpus run #332 will add;
  - provider/API charges;
  - runner/VM/GPU infrastructure charges where a candidate needs
    dedicated compute rather than a bare GitHub-hosted runner.
- **A free tier that cannot sustain expected usage is not automatically
  viable** — hitting its ceiling under normal activity and failing over
  to a paid tier (or failing closed) has to be evaluated like any other
  cost driver, not waved through because the label says "free."
- **Operational exit cost matters.** A viable runtime must be easy to
  disable — deleting a workflow/credential/config, not unwinding paid
  infrastructure left running or a dependency on the maintainer's
  personal machine/session left behind.

This spike did not re-run any candidate to measure §330 §5-style
per-invocation cost/latency at realistic PR-time/nightly scale — that
measurement is unresourced by a 2-case spike and does not change this
constraint's force. What it changes is how §7's recommendation is framed:
a fidelity win alone no longer settles the decision.

## 7. Decision

Class A (the `claude` CLI against the Anthropic backend) is this spike's
**fidelity baseline and current technical fallback** — not an
unconditional production recommendation. It is the only candidate that
demonstrated it can actually invoke the Skill's real semantics within a
bounded PR-check latency (§4–§5); candidate B did not, and is recorded as
**not viable in its current configuration**, independent of §6.

Whether class A can also satisfy §6's economic sustainability constraint
at realistic repository scale (PR-time cases, reruns, concurrent PRs, and
the future nightly/full-corpus run) was **not measured by this spike** —
that requires modeling or measuring cost at a scale a 2-case comparison
does not exercise. This decision record therefore does not clear class A
for unconditional provisioning:

- **#337 may provision class A only if it can produce a credible,
  bounded-cost design** — concrete per-PR/nightly cost bounds, hard
  ceilings (timeouts, case-count/concurrency limits, provider-side spend
  limits or a documented equivalent), and fail-closed behavior on
  timeout/quota/rate-limit/budget exhaustion — that plausibly stays
  within §6's constraints (strongly prefer $0 recurring; ~$40–50/month
  absolute ceiling; no plausible triple-digit-monthly-spend path under
  normal activity) and that can be disabled without leaving paid
  infrastructure or personal-machine dependencies behind.
- **If no such bounded-cost design is credible, the recommendation is not
  "provision class A anyway"** — it is to open further, separately
  time-boxed research into another class-B/C candidate (a different agent
  CLI, a different local/hosted open-weight model, or explicit
  agent-routing configuration a real spike could resolve) rather than
  silently accepting unbounded recurring spend on an unmaintained side
  project. Class A remains the safe fallback (per #330 §6) if that
  research does not clear fidelity either — but "safe fallback on
  fidelity" and "affordable to run indefinitely" are two different
  questions, and only #337's own cost design can answer the second one.
- No class-C candidate was available to test empirically in this
  environment; class C is recorded as **not evaluated**, not rejected,
  and remains a candidate for that further research if class A's cost
  design does not clear §6.

This spike does not implement any provisioning, does not reopen the
OpenCode/Ollama comparison, and does not change §4/§5's empirical
results — it only sets the bar #337's actual provisioning proposal must
clear before class A can be considered decided rather than provisional.

## 8. Bounded continuation: additional Class B/C candidates screened for §6

§6 was added after §7's original decision, so this section continues
#336 under that constraint rather than reopening §4/§5's empirical
results. Per #336's scope, this stayed a bounded screen — pricing/quota
research against current provider documentation, not new tuning of any
already-rejected candidate (§4's OpenCode/Ollama comparison, in
particular, was not reopened).

### 8.1 Screening results

Two source tiers are distinguished per claim below rather than treated as
uniform: **first-party** (fetched directly from the provider's own docs
or pricing page in this research) and **third-party** (a pricing-
aggregator/blog synthesis, not independently confirmed against a
first-party page — several providers gate their exact numeric free-tier
limits behind a logged-in dashboard, so no first-party *page* states
them at all). A third-party figure is flagged as such; it is a starting
estimate to re-verify against the provider's own account dashboard at
empirical-run time, not a settled fact.

| Candidate | Agent-capable | Skill fidelity path | CI/non-interactive | Quota vs. plausible usage | Personal-machine dependency | Outcome |
| --- | --- | --- | --- | --- | --- | --- |
| **Gemini CLI** (`google-gemini/gemini-cli`) + Gemini API | Yes — official open-source agentic CLI with file/shell tools | Untested; same throwaway-adapter approach as #336's other candidates would apply | Yes — **first-party**: `ai.google.dev`/`google-gemini.github.io` document a headless/`--non-interactive` mode built for CI/CD with `GEMINI_API_KEY`-based auth, isolable from any personal Google login | **Third-party estimate** (`ai.google.dev`'s own rate-limits/pricing pages defer exact numbers to a logged-in AI Studio dashboard, so no first-party page states them): ≈1,500 requests/day, 15 RPM, 1M TPM on a Flash model, no card | None — API-key auth, not session-based | **Screens favorably on the first-party-confirmed axes (agent capability, headless CI mode, credential isolation); kept for empirical follow-up (issue #366), which should also re-confirm the exact quota against the live AI Studio dashboard** |
| Groq API (paired with an agent CLI, e.g. `opencode`, via its OpenAI-compatible endpoint) | Yes (via a real agent CLI) | Untested | Yes | **Third-party estimate** (`console.groq.com/docs/rate-limits` confirms a Free Plan exists but explicitly defers exact figures to a logged-in account page): ≈6,000–12,000 TPM depending on model, ≈1,000–14,400 RPD. This repository's own Skill resources (`SKILL.md` + `policies/` + `shared/`) already total ≈555 KB / roughly 140K tokens if read broadly; even a partial read of the referenced sections plausibly exceeds a single free-tier TPM window in one turn at the estimated ceiling | None | **Rejected at screen** — even taking the third-party TPM estimate at face value, it is implausibly small against this Skill's real resource footprint; not run |
| OpenRouter free (`:free`-suffixed models, paired with an agent CLI) | Yes (via a real agent CLI) | Untested | Yes | **First-party** (`openrouter.ai/docs/api-reference/limits`, fetched directly): 20 requests/minute always; 50 requests/day with no credit purchased, 1,000/day after a one-time ≥$10 purchase. The docs make no uptime/reliability commitment for free models either way — that specific claim is dropped here rather than attributed to the provider | None | **Rejected at screen** — one agentic review plausibly consumes more than 50 requests by itself (each tool call is a request); no credible headroom for PR-time + rerun + concurrent-PR + nightly usage even at the 1,000/day tier |
| Cloudflare Workers AI | Uncertain — raw inference API; this survey did not find a first-party agent/tool-use CLI for it | Would require pairing with a third-party agent CLI, and tool-calling maturity for available models was not established | **Unproven as a whole** — the raw inference API is callable non-interactively (**first-party**: `developers.cloudflare.com/workers-ai/platform/pricing`), but no agent CLI to run it non-interactively against the Skill was established, so this axis is not actually cleared end-to-end | **First-party**: 10,000 Neurons/day free, no card stated. Neurons are a cross-model-type unit; a capable coding model's effective headroom in Neurons was not established in this survey | **Rejected at screen** — unproven agent/tool-use maturity; not a currently-real candidate by #330 §3's bar without more groundwork than this bounded screen allows |
| GitHub Copilot CLI | Yes | Untested | Yes (GitHub-native) | **First-party** (`github.com/features/copilot/plans`, fetched directly): Free plan lists Copilot CLI as an included feature (correcting this document's earlier claim that it is unavailable on Free) alongside "2,000 completions and 50 chat requests (including Copilot Edits)" per month; whether CLI usage draws from that same 50-request pool or a separately bounded allocation is not fully disentangled by the page | None (GitHub-native credential) | **Rejected at screen** — even under the most generous reading, Free-plan chat/agent-equivalent usage is capped at 50/month, far below one agentic review's request count; not rejected for unavailability (corrected) |
| Amazon Q Developer CLI | Yes | Untested | Yes | **First-party** (`aws.amazon.com/q/developer/pricing`, fetched directly): 50 agentic requests/month free, across chat/transformation/scanning combined | None | **Rejected at screen** — quota far below one agentic review's request count. (This document previously also cited a Pro-tier-closed/2027-sunset claim from a third-party source; AWS's own current pricing/tiers pages do not state this, so it is dropped here as unconfirmed rather than repeated) |

Every first-party citation above was fetched directly from the named
provider page during this research (September 2026); every third-party
estimate is named as such and should be re-verified against the
provider's own live account/dashboard figures before being relied on for
an empirical run or a production decision — not trusted from this table
indefinitely.

### 8.2 Why no additional empirical run happened here

Gemini CLI is the only candidate from §8.1 that clears the screen — it
is the sole survivor from a deliberately narrow additional search (5
candidates screened beyond the original #336 comparison), consistent
with #336's "prefer quality over quantity" bound. Actually running it
against the same two corpus cases requires a `GEMINI_API_KEY`, which is
not available in this environment; fabricating a fidelity/latency result
without running it would violate #336's own evidence-backed-decision
requirement. Rather than leave this open-ended inside #336, or block
#336's completion on obtaining a key, the empirical run is scoped into
[#366](https://github.com/amirbena/code-review-skill/issues/366) (Parent:
#336), a narrowly-bounded follow-up using the exact same corpus subset
and throwaway-adapter methodology this document already established.

### 8.3 Effect on §7's decision

§7's decision is unchanged by this section: class A remains the fidelity
baseline and current technical fallback, and no candidate has
empirically cleared §6's sustainability bar yet, so #337 still may
provision class A only with a credible bounded-cost design, or else wait
on further candidate research. Gemini CLI is now that further research's
concrete, scoped target (#366) rather than an open-ended "look for
something cheaper" instruction — if #366 empirically clears fidelity and
latency, its result should be folded back into this document's §7 as a
new recommendation for #337; if it does not, §7's class-A-fallback
framing stands as-is with one more ruled-out option recorded.

### 8.4 #366's empirical run: Gemini CLI

A `GEMINI_API_KEY` became available and #366's empirical follow-up ran.
Runtime/model/Skill-SHA metadata (#330 §5): `gemini` CLI `0.60.0`, Skill/repo
SHA `dec624d` (`main`), spike run date 2026-09-16.

**Method.** The same materialization and prompt approach §3 used for
candidate B (`opencode`) was reused: for each of the same two corpus
cases (`correctness-off-by-one-pagination`,
`no-op-comment-and-rename`), a throwaway workspace was materialized from
the case's `base` + `patch`, `skills/`, `policies/`, and `shared/` were
copied verbatim into it (the `gemini` CLI has no verified equivalent of
`--plugin-dir` for this checkout's non-plugin `skills/` layout, matching
candidate B's constraint), and `gemini` was invoked non-interactively
(`-p`, `--output-format text`, `--approval-mode yolo`, `--skip-trust`)
with the same canonical-rendering prompt candidate A/B used, pointed at
the copied `SKILL.md`. Neither adapter/workspace is committed to the
repository, per #336's scope.

**Result — both cases: quota-exhausted, no review produced.**

| Case | Result | Latency |
| --- | --- | --- |
| `correctness-off-by-one-pagination` | No review report. First attempt (default model) failed after repeated `429`/`503` retries with `TerminalQuotaError: You have exhausted your daily quota on this model` against `generativelanguage.googleapis.com/generate_content_free_tier_requests`, `model: gemini-3.5-flash`. A second attempt explicitly passing `-m gemini-2.5-flash` **still exhausted the same `gemini-3.5-flash` quota bucket** — the CLI's automatic model routing for agentic/tool-using turns did not honor the explicit `-m` override observed to work for a non-tool-use probe prompt (see below). | 3m21s (default model, first attempt); 3m31s (`-m gemini-2.5-flash`, second attempt) |
| `no-op-comment-and-rename` | Same `TerminalQuotaError`, now failing immediately (daily quota already exhausted by the two prior attempts) rather than after retries. | 11.2s |

**Supporting observation.** A separate, non-agentic probe (`gemini -m
gemini-2.5-flash -p "reply with the single word: ok"`, no file/tool use)
against the same key succeeded in a few seconds. This isolates the
failure to agentic/tool-using turns specifically hitting a shared,
already-low daily quota bucket (observed limits in the error payloads:
5 requests/minute and 20 requests/day for `generate_content_free_tier_requests`,
and 250,000 for `generate_content_free_tier_input_token_count`) — not to
CLI installation, authentication, or basic connectivity, all of which
worked. This 20-requests/day figure is far below the ≈1,500
requests/day the issue's problem statement and §8.1's table cited as a
**third-party estimate** for "a Flash model" — that estimate did not
hold for the actual default-routed model (`gemini-3.5-flash`) or key
tier exercised here; §8.1's own caveat that third-party figures need
re-verification against a live account is exactly what this run surfaced.

**Scored against #330 §4's viability criteria.** Every criterion that
depends on a completed review (inspecting the repo, executing the
Skill's tools, invoking the Skill's real semantics, bounded PR-check
latency, reproducibility of a *result*) is **not demonstrated** — not
because the CLI failed to launch or reach the workspace (both attempts
did start, load tools, and begin agentic turns per the `err` logs before
the quota error), but because no case ever received a completed model
response to review against. This is a different failure mode than
candidate B's (which never reached the Skill content at all): Gemini CLI
did engage the workspace and begin an agentic turn, it simply could not
complete one before the account's daily quota — as actually provisioned
for this key — was exhausted.

**Effect on §7's decision: unchanged.** This run does not clear Gemini
CLI's fidelity/latency bar (no case produced a parseable review), and it
does not reject it either in the sense §4 rejected candidate B (no
evidence the Skill's semantics can't be invoked — only that this key's
free-tier quota couldn't sustain even two small cases run sequentially
in one sitting). Per the Acceptance Criteria this issue set for itself:
class A remains the sole empirically-cleared fallback, and §7's decision
stands unchanged. Whether a different Google Cloud project/billing tier,
a paid Gemini API tier, or quota-reset timing would let Gemini CLI clear
fidelity was **not tested** — that is further research, not something
this bounded, time-boxed spike re-runs today (per #336's explicit
time-box and this issue's Non-Goals, which exclude "re-evaluating any
candidate #336 already rejected" but do not obligate an unbounded number
of retries against an exhausted quota either).

## 9. Known gap surfaced by this spike

Neither `ProductionReviewerAdapter` nor `run_benchmark.py` currently
records the model/backend identifier its `claude` CLI invocation actually
used (#330 §5's second metadata bullet) — only the CLI name/version is
observable today. This spike could only report "the default model
configured for the CLI in this environment" for candidate A. Wiring the
actual model identifier into `run_benchmark.py`'s output is provisioning
work for #337, which already owns wiring the full §5 metadata rule in
(per [`runtime-execution-contract.md`](runtime-execution-contract.md) §5);
this is not a new requirement, just a concrete gap #337 should close.

## 10. Out of scope

- Re-running the full corpus (#336 non-goal; a small, fixed subset is
  sufficient).
- Building a production-quality adapter for candidate B, or any further
  OpenCode/Ollama tuning (#336 non-goal and explicit time-box) — §6/§8 do
  not reopen this either.
- Measuring actual per-invocation cost at PR-time/nightly scale, or
  designing the bounded-cost mechanism itself (provider spend limits,
  timeouts, concurrency caps) — that is #337's provisioning work, guided
  by §6's constraint, not this spike's.
- Re-running Gemini CLI against a different key, billing tier, or after
  quota reset to chase a completed fidelity result (§8.4) — out of
  #366's time-box; a candidate follow-up issue, not this spike.
- Running any other §8.1 candidate empirically beyond Gemini CLI.
- An open-ended vendor survey beyond §8.1's bounded shortlist.
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
  provisioning, which must satisfy §6's bounded-cost constraint before
  class A is provisioned, or else open further class-B/C research per §7.
- [#366](https://github.com/amirbena/code-review-skill/issues/366) —
  the narrowly-scoped follow-up (Parent: #336) that empirically ran
  Gemini CLI, the one candidate §8 found worth testing; see §8.4 for the
  result (quota-exhausted on both cases, §7's decision unchanged).
