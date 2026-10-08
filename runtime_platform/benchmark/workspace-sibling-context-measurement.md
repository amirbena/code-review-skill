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
| Acceptable cost | Median `on` run time is at most `2.0` times the median `off` run time, and the same for tokens. Token data is required: if any executed run in either arm has no token count, the criterion is `not-evaluated` (unless a ratio that could be computed already fails). |

Outcome per adapter:

- `fail` if any criterion fails.
- `not-evaluated` if a case has fewer than 2 executed runs in an arm, or any
  criterion could not be evaluated, missing token data included.
- `pass` otherwise.

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

### Harness isolation and evidence (added after the first record)

The first record ([#664](https://github.com/amirbena/code-review-skill/issues/664),
`not-evaluated`) was not interpretable because the harness did not establish
which skill ran. The thresholds and gate in section 5 are unchanged; only the
harness changed.

- **Skill isolation.** `measure_workspace_sibling.py` runs the local adapter with
  `ProductionReviewerAdapter(verified_isolation=True)`: `--setting-sources
  project,local` (no user-level settings, so no installed plugin loads) and
  `--output-format stream-json --verbose`. The `init` event is then checked and
  the run **fails closed** unless exactly one `local-code-review` skill exists,
  it comes from the inline plugin loaded from this checkout, no other
  non-builtin plugin is loaded, and every skill call went to it. A run that
  cannot establish this is an `isolation-failed` error, and the script stops at
  the first one (exit 2) rather than spending the rest of the runs.
- **The grant is also a permission.** The CLI blocks reads outside its working
  directories, so with a grant the adapter passes `--add-dir <workspace root>`.
  Before this, a reviewer that did try to list the root was blocked.
- **Evidence.** Each run writes `<adapter>-<case>-<arm>-<n>.json` plus raw
  `.stdout`/`.stderr` under `--evidence-dir`: exit code, error category, argv
  with the prompt replaced by its hash, skill identity and checkout revision
  (and whether the tree was dirty), CLI version and model, usage, and the tool
  trace. Failed runs keep theirs. An existing `--out` or non-empty evidence
  directory is never overwritten; `--retry-of` links a new record to the one it
  follows. A timeout leaves no raw streams (the termination helper discards
  them), only the category.
- **Capability activation.** Each `on` run records four separate levels from the
  reviewer's own tool calls: root supplied, root discovered, sibling inspected,
  sibling content read. Supplying the argument is not use. The record carries a
  `capability_activation` count per adapter. It is informational and never an
  input to the gate; whether a record in which no `on` run read a sibling should
  make quality gain `not-evaluated` is a gate-semantics decision for the
  maintainer. Relevance of what was read is not judged mechanically.
- **Absence claims.** The heuristic no longer counts an existence statement
  bounded to the reviewed repository, a named source, or a sibling the evidence
  shows was inspected. A conclusion ("safe to ship") is exempt only when scoped
  to a repository at a revision.
- **Cost.** The stream-json result event reports token usage, so `tokens` is now
  recorded where the local adapter runs. `input_tokens` is the whole prompt
  context (fresh plus cache creation plus cache reads); the fresh part alone is
  a few tokens and would hide the real context cost. The breakdown is kept in
  each run's evidence. Token data is required by the cost criterion: a
  caller-supplied adapter that reports nothing, or a single run without a
  count, makes the criterion `not-evaluated` and so the adapter's outcome
  `not-evaluated`; it is never an implicit pass. This resolves the earlier
  tension between this section and the acceptance criteria of #664 in favor of
  the criteria. The `2.0` thresholds are unchanged.
- **Fixture amendment (pairing).** The first smoke run produced the intended
  finding (same location, the exhaustive consumer raising on `refunded`, the
  sibling cited as evidence) but it was not paired: the reviewer named the class
  `breaking-enum-extension`, and the matcher's slug-compatibility rule (a
  subset relation over kebab tokens, [`match-criteria.md`](match-criteria.md)
  §4) cannot relate that to the fixture's long primary slug. The two describe
  one defect, so `wsib-resolves-from-relevant-sibling` and
  `wsib-gh-published-output-reference-only` (which restates the same finding)
  gain a documented `alternatives` entry with that slug, the mechanism
  [`fixture-format.md`](fixture-format.md) §8.2 provides for a restated defect.
  The matcher, the primary spec, and every threshold are unchanged. A finding
  that only says the consumer is *unverified* (the no-sibling behavior) remains
  unmatched; a test pins that.
- **Provenance of the revision.** A measurement refuses to start when the skill
  checkout has uncommitted tracked changes (or git cannot say), so the record's
  skill revision names the code that ran; `--allow-dirty` overrides it for a
  harness check, and `--smoke` is exempt. Each record stores the skill identity
  and `skill_tree_dirty`. A stream failure (no events, or isolation not
  established) stops the whole run at once.
- **Evidence handling.** Raw `.stdout`/`.stderr` contain local paths and full
  tool traces. They are retained next to the record and are not attached to a
  public issue as they are; attach the record and a reviewed summary.
- **Smoke.** `--smoke --case <id> --runs 1` checks the harness with one off/on
  pair and records `smoke: true`. It is not a measurement and yields no verdict.

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
