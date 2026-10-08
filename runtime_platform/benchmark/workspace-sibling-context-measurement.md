# Workspace sibling context measurement

Decision record, comparison protocol, and pre-registered gate for
[#664](https://github.com/amirbena/code-review-skill/issues/664) (child C3 of
[#661](https://github.com/amirbena/code-review-skill/issues/661)). It measures
whether the capability in
[`../../shared/policies/workspace-sibling-context.md`](../../shared/policies/workspace-sibling-context.md)
improves review outcomes in **both** review adapters, or only adds context
cost, and whether it adds unjustified certainty when the evidence is thin.

Repository-development measurement only. Nothing here is packaged, and no
Skill rule, baseline, matcher, or capability semantic changes.

## 1. What is reused

| Existing piece | Reused for |
| --- | --- |
| [`structured-result-runtime-properties.md`](structured-result-runtime-properties.md) (#529) | The on-demand, maintainer-run on/off shape: alternating arms, a fixed run count per arm, a verdict that treats too few executed runs as `not-evaluated`, a record attached to the PR or issue and not committed. |
| The #605 comparison (search-only versus enriched, same #602 corpus) | Pre-registration: the decision rule is stated before any run, both arms use identical fixtures, false-positive growth and a control are part of the rule. |
| [`../../benchmark/corpus/relationship-recall/`](../../benchmark/corpus/relationship-recall/README.md) (#602) | The case-class pattern (positive, control, unresolvable) and outcome vocabulary (correct, missed, wrong, not observed). |
| [`fixture-format.md`](fixture-format.md), [`reference/benchmark_fixture.py`](reference/benchmark_fixture.py) | The one fixture format and validator; the cases are `benchmark-case/v2`, indexed in [`corpus-index.json`](../../benchmark/corpus-index.json). |
| [`runner-contract.md`](runner-contract.md), [`reference/benchmark_runner.py`](reference/benchmark_runner.py) | Execution. `run_case` is unchanged apart from materializing the new input. |
| [`missed-and-incorrect-findings.md`](missed-and-incorrect-findings.md) (#55) | Pairing: `missed` is a required expected entry without a match, `wrong` is a produced finding no entry consumed. |
| The #133 `input.external_contexts` seam | The materialization and keyword-forwarding pattern for non-member repositories. |

No new matcher, scorer, validator, lane, or CI gate is introduced.

### The one additive fixture input

`input.workspace_siblings` ([`fixture-format.md`](fixture-format.md) §6.6)
materializes repositories as immediate children of one workspace root.
`external_contexts` cannot express this: it hands a path and a pinned revision
per repository, the opposite of one granted root the reviewer chooses within.
The input is optional and valid only with `patch`, so every existing case is
unchanged. It is coordinated with #133 by reusing its direction: the runner
passes a keyword (`workspace_root`) only to a case that declares the input.

## 2. Adapters: what is shared and what is per adapter

The case classes and the security regressions are adapter-independent, so each
**shared** case is written once and run through each adapter. Cases that
differ are GitHub-only and carry the `wsib-gh-` id prefix.

| Coverage | Cases |
| --- | --- |
| Shared, run once per adapter | resolution, no relevant sibling, ambiguous sibling, insufficient evidence, absence in an inspected sibling, unrelated sibling |
| `github-pr-review` only | PR repository excluded by identity, API-only mode (grant unavailable, behavior unchanged), no sibling content in published output |

The local adapter is the production reviewer adapter. The GitHub adapter is
caller-supplied to the measurement script, as the issue requires: this
repository has no production GitHub reviewer adapter. A supplied adapter is a
callable accepting the optional `workspace_root` keyword that exposes
`last_report` and, when it can, `last_usage`. A GitHub adapter that is not
supplied is recorded `not-run`; its outcome is never inferred from the local
adapter's.

## 3. Arms

Both arms materialize the **same** siblings on disk from the **same** fixture.
They differ in one thing: the `on` arm forwards `workspace_root` to the
reviewer, the `off` arm withholds it. Runs alternate off, on, off, on so slow
drift in the runtime or model lands on both arms. Default `3` runs per arm per
case; `2` is the minimum for any verdict.

The ordinary benchmark runner always forwards the root, so these cases run in
the capability-on configuration there. Adding the sub-corpus enlarges the
comprehensive corpus once, which gives the scheduled comprehensive lane a new
`corpus_id` and a bootstrap baseline. That is ordinary corpus growth, not a
redefinition of any baseline or gate.

## 4. What is measured

Per run, from the #55 pairing and the report text:

| Measure | Definition |
| --- | --- |
| `found` / `missed` | required expected findings paired / not paired |
| `wrong` | produced findings no expected entry consumed (a finding where none is expected is unjustified certainty) |
| `escalated` | the report's Context gaps or Reasoning check text still mentions the open question (`refunded`) |
| `absence_claim` | the report matches the absence-claim phrases in [`reference/benchmark_workspace_sibling.py`](reference/benchmark_workspace_sibling.py) |
| `leaked` | the planted sibling marker appears in the output |
| `seconds`, `tokens` | wall-clock per run; input plus output tokens when the adapter reports them, otherwise `null` |

The `escalated`, `absence_claim`, and `leaked` checks are text heuristics. They
are conservative for the property they guard and are read with the recorded
output, never as a proof. The absence phrase list is a closed, committed
list: a sentence that names a repository at a revision (`repo@sha`) is a
bounded search statement and is not counted; a differently worded absence
claim is not detected, so a `pass` on that
criterion means "no listed phrase", and a maintainer reads the `absence` case
output before accepting it.

## 5. Pre-registered gate

Committed before the first measured run. Evaluated **per adapter** and never
averaged across adapters. Counts are over executed runs only.

| Criterion | Passes when |
| --- | --- |
| Quality gain | In the resolving case, the share of `on` runs that find the required finding is at least `2/3` **and** exceeds the `off` share. |
| False-positive growth | Total `wrong` in the `on` arm over the guarded cases (fallback, ambiguous, insufficient, absence, unrelated, and the GitHub identity and API-only cases) does not exceed the `off` total. |
| Preserved escalation | Over the escalation cases, the share of `on` runs that still escalate is at least the `off` share. |
| No absence claim | No `on` run of the absence case matches an absence-claim phrase. |
| No published sibling content | GitHub only. No `on` run of the published-output case contains the sibling marker. |
| Acceptable cost | Median `on` run time is at most `2.0` times the median `off` run time, and the same for tokens where the adapter reports them. A token ratio the adapter cannot report is `not-evaluated`. |

Outcome per adapter:

- `fail` if any criterion fails.
- `not-evaluated` if a case has fewer than 2 executed runs in an arm, or any
  criterion other than a missing token ratio could not be evaluated.
- `pass` otherwise. A missing token ratio alone is stated in the record and
  does not block `pass`.

A failed gate is the result. The thresholds above are not adjusted after a run
to make the capability pass; changing one requires a new decision record before
the next run.

## 6. Running and recording

```bash
python3 runtime_platform/benchmark/scripts/measure_workspace_sibling.py --out measurement.json
python3 runtime_platform/benchmark/scripts/measure_workspace_sibling.py \
    --github-reviewer my_package.adapters:make_github_reviewer --runs 5 --out measurement.json
```

The record `workspace-sibling-context-measurement/v1` carries the skill SHA,
runtime, model label, every run (the #55 `found`, `missed`, `wrong` counts plus
the cost fields above), and one gate outcome per adapter. The
[`benchmark-result/v1`](benchmark-result-schema.md) record seals scheduled lane
runs and has no slot for an on/off arm or per-run cost, so, as with #529, this
on-demand record is attached to the PR or issue and not committed. The exit
code reflects execution health only.

## 7. Status

The design, fixtures, and gate are committed. **No measured run is recorded
yet**: every run is a live model invocation, and a maintainer runs the command
above and attaches the record to #664. Until then neither adapter has a gate
outcome, and the capability's #661 acceptance criterion on the benchmark gate
stays open.

## 8. Non-goals

- No new scheduled lane or required CI gate. A lane is justified only if the
  recorded result shows a drift worth watching.
- No change to capability semantics, baselines, the matcher, or the gate after
  a run.

## 9. Files

| File | Role |
| --- | --- |
| [`../../benchmark/corpus/workspace-sibling-context/`](../../benchmark/corpus/workspace-sibling-context/README.md) | The nine cases and their adapter coverage. |
| [`reference/benchmark_workspace_sibling.py`](reference/benchmark_workspace_sibling.py) | Test-only reduction of runs to the per-adapter gate outcome. |
| [`scripts/measure_workspace_sibling.py`](scripts/measure_workspace_sibling.py) | Maintainer entrypoint: arms, adapters, the record. |
| [`../../tests/unit/benchmark/test_workspace_sibling_corpus.py`](../../tests/unit/benchmark/test_workspace_sibling_corpus.py) | Corpus, materialization, adapter seam, and gate-rule tests. |
