# Structured-result runtime properties

Decision record and measurement contract for
[#529](https://github.com/amirbena/code-review-skill/issues/529). It covers
two properties of the opt-in structured review result
([#69](https://github.com/amirbena/code-review-skill/issues/69)) that no
check on a single output can see, including the
[#71](https://github.com/amirbena/code-review-skill/issues/71) contract
tests:

1. **The `stable_id` is computed.**
   [`structured-output.md`](../../shared/policies/structured-output.md),
   "Finding identity", requires the digest to come from a shell hashing
   command. The result does not carry the descriptor inputs, so an invented
   `fid_v1_<32 hex>` passes every #71 check.
2. **The option is output-only.** The same policy, "Activation", says
   findings, severity, coverage, and the Decision are identical with the
   option on and off.

Repository-development measurement only. Nothing here is packaged, and no
Skill rule changes.

## 1. Decision

**Adopted** as an on-demand measurement a maintainer runs by hand. It is
not a benchmark lane, not scheduled, and not a gate. Run it after a change
to `structured-output.md`, the finding-identity contract, or the local
review runbook's output steps, and before any consumer starts depending on
`stable_id` across reviews.

Reasons for adopting it rather than declining:

- Both properties are promises the policy makes to consumers. A consumer
  that joins findings across reviews by `stable_id` breaks silently if the
  value is invented.
- The existing pieces already do the hard parts: the runner isolates each
  run, the [#55 pairing](missed-and-incorrect-findings.md) decides which
  produced finding is which expected finding, and the #71 comparator checks
  schema conformance and report ↔ result agreement. The measurement adds
  only the cross-run comparison.

Reasons it stays on-demand: every run is a live model invocation, the
subset needs 24 of them, and the result needs a maintainer's reading
(section 5), not an automatic pass/fail.

## 2. Fixture subset

Four existing corpus cases, fixed in
[`scripts/measure_structured_result.py`](scripts/measure_structured_result.py):

| Case | Why |
| --- | --- |
| `dd-blocking-p0-sql-injection` | One unambiguous P0. The finding recurs reliably, so its `stable_id` can be compared. |
| `dd-blocking-p1-inverted-error-rate` | One P1 whose claim can be worded in several ways. It tests whether wording drift moves the ID. |
| `quality-duplicated-branch-logic` | A P2 on a clean decision. The policy says P2 findings are serialized on a clean review, and the option must not flip the decision. |
| `no-op-comment-and-rename` | No findings. The option must not invent a finding or change a clean decision. It adds nothing to property 1. |

Together they cover P0, P1, P2 and an empty review, and both decisions.
Larger or repository-reference cases add cost without adding a new shape.

## 3. Run count and order

`3` runs per arm per case, so 6 runs per case and 24 in total. Two runs
are the minimum for a stability comparison. The third run lets a single
outlier show up as variance instead of deciding the verdict. `--runs`
raises the count when a first measurement is inconclusive.

The arms alternate (off, on, off, on, …) so that slow drift in the
runtime or model spreads over both arms instead of landing on one.

Both arms use the same allowlist: the benchmark's read-only
`Bash(git *) Read Grep Glob` plus `Bash(printf *) Bash(shasum *)
Bash(sha256sum *)`. The ordinary benchmark allowlist cannot run the
hashing step the policy requires. Widening it for the on-arm only would
make the allowlist a second variable next to the option.

## 4. What is recorded

One JSON document, `structured-result-runtime-properties/v1`, with the
runtime, the model label, the allowlist, and this checkout's SHA. For each
run:

- the decision, from the rendered label (the
  [#350](https://github.com/amirbena/code-review-skill/issues/350)
  classifier);
- the paired expected entries with their produced severity, and the
  severities of unpaired produced findings (the #55 pairing);
- for on-runs, the #71 `contract_errors`, and the `stable_id` and claim
  text of each paired finding.

A `stable_id` is attributed to an expected entry only when the #71 checks
pass and the report parser kept every finding. Only then does finding *i*
of the report correspond to finding *i* of the result. Otherwise the run
records a contract error and adds nothing to property 1.

The `summary` block lists what a reader checks first: `stable_id_flags`,
`option_dependent`, `inconclusive`, `not_evaluated`, and
`contract_errors`.

## 5. Variance handling and reading the result

### Property 1: `stable_id`

For each expected entry paired in at least two on-runs:

| Status | Meaning |
| --- | --- |
| `stable` | one distinct `stable_id` across the runs |
| `unstable` | more than one; raised as a flag |
| `insufficient-runs` | paired in fewer than two runs |

Two more flags come from single runs. `example-copy` means the run emitted
the illustrative `stable_id` from the policy's example. `collision` means
one `stable_id` was given to findings paired with different expected
entries.

`unstable` does not prove fabrication. The descriptor includes
`cause_key` and `behavior_key`, which are tokenized from the finding's own
claim text. If two runs word the claim differently, the ID changes even
when both digests were computed correctly. Read an `unstable` flag with
the run's recorded `claims`. A changed ID with the same wording points
to fabrication. A changed ID with different wording is descriptor drift,
which the identity contract allows. `example-copy` is direct evidence of
an invented value. `collision` is strong evidence, because paired entries
differ in location or mechanism and so should not reduce to one
descriptor.

A `stable` result does not prove the value was computed either: a run that
derives a fixed fake value from the title would also be stable. Deciding
that needs the tool-call transcript (whether a hashing command ran). The
adapter reads only the text reply, so that check is deferred until a
consumer needs a stronger guarantee.

### Property 2: option invariance

Four components are compared across arms: `decision`, `finding_set`
(paired entry keys), `severities` (paired keys with severity), and
`unpaired` (severities of extra findings). For each component, the set of
values seen in the on-arm is compared with the set seen in the off-arm:

| Verdict | Rule | Reading |
| --- | --- | --- |
| `consistent` | the two sets are equal | no difference beyond the variance both arms share |
| `divergent` | each arm repeats one value, and the values differ | the option changed the review; listed in `option_dependent` |
| `inconclusive` | anything else | run-to-run variance the run count cannot separate from an option effect; rerun with a higher `--runs`, never read as a pass |
| `not-evaluated` | an arm has no executed run | nothing measured |

A case takes its worst component verdict. The rule is deliberately strict
about calling a difference an option effect. A `divergent` verdict needs
every run in each arm to agree, so ordinary variance rarely produces it.

## 6. Running it

```bash
python3 runtime_platform/benchmark/scripts/measure_structured_result.py --out measurement.json
```

`--case-id` limits the run to part of the subset. `--model` records a model
label. The exit code reflects execution health only. It is 0 when every
run executed, 1 when a run errored, and 2 when the runtime is unavailable
or `--runs` is below 2. Flags never change the exit code.

The record is evidence for a maintainer. Attach it to the PR or issue that
prompted the run, and do not commit it to the repository.

## 7. Non-goals

- No structured output in the ordinary benchmark: `run_benchmark.py` and
  the scheduled lanes still run with the option off and score only the
  Markdown report ([`review-result-model.md`](../../docs/review-result/review-result-model.md)
  section 8).
- No change to the sentinel cases, the metrics, or the lanes.
- No live `github-pr-review` runs; that Skill has no structured-result
  surface.

## 8. Files

| File | Role |
| --- | --- |
| [`reference/benchmark_structured_result.py`](reference/benchmark_structured_result.py) | Test-only reduction of runs to the two verdicts and the record. |
| [`scripts/measure_structured_result.py`](scripts/measure_structured_result.py) | Maintainer entrypoint: the subset, alternating arms, the record. |
| [`scripts/benchmark_review_adapter.py`](scripts/benchmark_review_adapter.py) | Gains opt-in `structured_review_result` and `allowed_tools` arguments. Its defaults are unchanged. |
| [`../../tests/unit/benchmark/test_structured_result_properties.py`](../../tests/unit/benchmark/test_structured_result_properties.py) | Rule tests plus a stub-CLI run through the real adapter, runner, matcher, and #71 comparator. |
