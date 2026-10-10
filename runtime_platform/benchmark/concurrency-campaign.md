# Concurrency Measurement Campaign (Issue #682)

Pre-registered configuration of the four-experiment campaign run by the temporary routine in
[`concurrency-experiment.md`](concurrency-experiment.md) ([#681](https://github.com/amirbena/code-review-skill/issues/681)),
parent [#680](https://github.com/amirbena/code-review-skill/issues/680), measured by
[#682](https://github.com/amirbena/code-review-skill/issues/682), closed out by
[#683](https://github.com/amirbena/code-review-skill/issues/683). Everything below is committed in
[`schedule/concurrency-experiment-spec.json`](schedule/concurrency-experiment-spec.json) **before the first run** and is not
changed afterwards. Repository-development document; not packaged into either Skill archive.

## 1. Fixture subset

| Fact | Value |
| --- | --- |
| Corpus at selection | 144 `benchmark-case/v2` fixtures, `corpus_id` `44d3d405…a1a013f` (the #680 text still quotes 133) |
| Subset | 24 fixtures, `subset_id` `fa240faf…310c45`, listed as `subset.case_ids` and verified on every run |
| Workers | 24 fixtures leave 6 per worker at 4 workers and 12 at 2 |

**Timing evidence is insufficient.** No per-fixture duration, interrupted-run elapsed time or provider window is stored in the
repository. The only latency figures are the 26–35 s of a 2-case spike (#680) and the maintainer's unconfirmed "30 minutes" wording
(#611). The subset is therefore stratified on structural proxies, not measured cost, and "historically slow" is not claimed.

**Method.** Strata are filled in this order, each taking the fixtures not yet chosen, ranked by `sha256("concurrency-campaign-682-v1:" + case_id)`:

| Stratum | Count | Rule | Why |
| --- | --- | --- | --- |
| `large-patch` | 1 | patch touches ≥ 10 files | the only expensive-input case (11 files, 6 KB) |
| `wide-context` | 4 | has `workspace_siblings`, `repositories`, `external_contexts` or `unadmitted_repositories` | extra repositories and context reads |
| `security` | 3 | tag `security` | security reasoning |
| `concurrency` | 3 | tag `concurrency` | concurrency and distributed reasoning |
| `performance` | 2 | tag `performance` | performance reasoning |
| `architectural` | 3 | `specialist-depth-composition`, `risk-depth`, `semantic-implication`, `api-compatibility` | multi-capability depth passes |
| `multi-file` | 2 | patch touches ≥ 2 files | cross-file reasoning |
| `no-finding` | 4 | expects `clean` with no findings | no-finding expectations |
| `fast-single-file` | 2 | one file, input at or below the 25th percentile | the cheap end |

The result mixes 12 `clean` and 12 `changes-required` expectations across 15 of the corpus's 24 sub-corpus directories. Cost tiers are proxies: fast (`fast-single-file`, `no-finding`), medium (single-file reasoning strata) and expensive (`large-patch`, `wide-context`, `multi-file`).

**Expected sequential cost (not measured).** At the 26–35 s spike rate one arm costs 24 × 26–35 s ≈ 10–14 min, so Tuesday's `[1,2]` experiment
is about 16–21 min and Thursday's `[2,4]` about 9–12 min. This is an extrapolation from two cases. If the expensive strata
cost several times more, the `1`-worker arm may exceed an unknown window; the first Tuesday result is the first real evidence.

**Coverage limitations.** The subset cannot show how a full run behaves: 24 of 144 fixtures is a short sample, contention may grow with a longer run,
9 sub-corpus directories (for example `api-compatibility`, `database-migration-deepening` and `dependency-supply-chain-deepening`) have no fixture in it, and token cost is not measured.

## 2. Thresholds

Classes decide what a failure means. Defaults were proposed in #682 and are fixed here; they are ratified by merging this change.

**Hard safety gates** (any failure → NO-GO; they can never be relaxed, and the validator rejects any other value):

| Gate | Threshold |
| --- | --- |
| Isolation violations, all experiments | `0` |
| Valid per-fixture results (completed ÷ planned, all arms) | `1.0` (so execution errors and timeouts are also `0`) |
| Experiment completeness | every experiment `status` is `complete` and ran every planned arm |
| Provenance | `repo_sha`, `model_id`, `runtime_version`, `subset_id`, `corpus_id` identical across experiments, and `repo_sha` equal to the pin |

**Performance decision thresholds** (not all met → not GO):

| Threshold | Value | Outcome when missed |
| --- | --- | --- |
| Meaningful speedup: best pair of arms | ≥ 1.15× | NO-GO |
| Scaling efficiency (speedup ÷ worker ratio), mean over a worker count's pairs | ≥ 0.60 at 2 workers, ≥ 0.45 at 4 | that worker count is not eligible |
| Same-configuration wall-clock coefficient of variation (the four 2-worker arms) | ≤ 0.25 | INCONCLUSIVE |
| Cross-worker-count outcome disagreement above the same-configuration baseline | ≤ 0 | INCONCLUSIVE |
| Rate-limited fixtures at a worker count | ≤ 5 % of attempted | that worker count is not eligible |
| Projected full-corpus time (per-fixture wall × (corpus size + 20 worst-case confirmation invocations)) | ≤ 60 % of the evidenced window | that worker count is not eligible |

*Outcome* is the number of findings a fixture produced. Disagreement is the share of fixtures whose count differs between two arms, and the baseline is the largest disagreement between two 2-worker arms.

**The window is not assumed.** `window.evidenced_window_s` is `null`. Until a real elapsed-at-SIGTERM figure is recorded, the window check is unmeasured and the decision cannot be GO. Setting it is a decision change and needs a new spec before the first run, never after.

**Diagnostic indicators** (reported, never gating): per-fixture median and maximum time, peak 1-minute load and child CPU, raw rate-limit hit and timeout counts, and the review CLI state fingerprint. `rate_limit_hits` counts only what the child surfaces; zero is not proof of no throttling.

**GO / NO-GO / INCONCLUSIVE.** GO: every hard gate and every campaign-wide threshold (speedup, variance, disagreement) met and at least one worker count eligible; a worker count that misses its own efficiency, rate-limit or window threshold is only ineligible and does not block another. NO-GO: a hard gate or the speedup floor fails. INCONCLUSIVE: everything else, including fewer than four valid experiments. A missed run stays missed, and an extension needs explicit maintainer authorization in an issue and a new spec. Report projections, measurements and verified completion separately: a projection is not a sealed Comprehensive run, and GO only authorizes a separate production issue.

[`benchmark_concurrency_decision.py`](scripts/benchmark_concurrency_decision.py) implements `validate_spec` (run before every execution) and `evaluate_campaign`, which turns the four sealed `concurrency-experiment.json` records into the decision. Its input is the records under `claude/concurrency-experiment-*` only, never `claude/concurrency-trial-*`; the projection extrapolates the subset's per-fixture mean to the full corpus and says so in its output.

## 3. Schedule

| Date | Weekday | Arms |
| --- | --- | --- |
| 2026-10-13 | Tuesday | `1`, then `2` |
| 2026-10-15 | Thursday | `2`, then `4` |
| 2026-10-20 | Tuesday | `2`, then `1` |
| 2026-10-22 | Thursday | `4`, then `2` |

12:00 `Asia/Jerusalem`, `max_experiments` 4, `window_end` 2026-10-22 (the last experiment). Week two reverses every arm order so order, cache warmth and time of day do not favour one count; the validator enforces that. The entrypoint refuses any other date, any date after `window_end`, a fifth experiment ref and a second run on one day, whether or not the Routine is still enabled.

## 4. Pinned source

The campaign must run one immutable commit that contains this configuration. That commit cannot be written into the spec it belongs to, so the pin is supplied from outside the commit:

1. The maintainer merges this change and records the **merge commit SHA** in the activation comment on #682.
2. The Routine checks out exactly that SHA and passes it as `--pinned-sha <sha>`.
3. A scheduled run fails with exit 1 before selecting or executing any fixture unless the flag is a full 40-character lowercase SHA, equals `HEAD`, and the working tree is clean. Each sealed record carries the value as `provenance.pinned_sha`, and the evaluator rejects experiments whose `repo_sha` differs.

A run skipped by the stop condition does not need the flag.

## 5. Activation

```text
TEMPORARY (#681): four two-week concurrency measurement experiments, then is disabled.
1. Check out a fresh copy of amirbena/code-review-skill at exactly <PINNED_SHA>. Do not update it.
2. Run:
   python3 runtime_platform/benchmark/scripts/run_concurrency_experiment.py \
     --trigger scheduled \
     --pinned-sha <PINNED_SHA> \
     --model-id <the model backend this Routine session is running as>
3. If the command exits non-zero, stop — do not report success, do not retry, and do not
   post or push anything else to GitHub. Keep the command's stdout and stderr in the transcript.
```

The evidence destination is the manifest's `evidence` block ([`private-evidence-repository.md`](scheduled-operations/private-evidence-repository.md) §4, §14). Under `pre_cutover` the prompt above is unchanged; once the phase is `private` the prompt must also pass `--evidence-remote <evidence-repository-remote>` (a credential-free remote), and a run without it exits 2 and writes nothing. An unreachable store exits 3, and the stop condition counts only that store.

Routine: Tuesday and Thursday 12:00 `Asia/Jerusalem`, ending after 2026-10-22; cron `0 12 * * 2,4`. Registering it is a maintainer-only provider-side step, not part of this change.
