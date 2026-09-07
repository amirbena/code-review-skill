# Benchmark Regression Report

Repository-development contract for GitHub Issue
[#53](https://github.com/amirbena/code-review-skill/issues/53). It defines
**how a candidate benchmark run is compared against a stored baseline run
and what that comparison emits** — the baseline result artifact, the
per-case and aggregate deltas, the rule that separates a *regression* from
an *improvement*, deterministic output, and the deliberate baseline-refresh
step. It consumes the machine-readable per-case result shape fixed by the
runner contract ([`runner-contract.md`](runner-contract.md) §6, #52),
which in turn builds on the fixture format
([`fixture-format.md`](fixture-format.md), #50) and the corpus
([`corpus/README.md`](corpus/README.md), #51). Parent capability:
[#40](https://github.com/amirbena/code-review-skill/issues/40).

Like [`runner-contract.md`](runner-contract.md) and the rest of
[`./`](README.md), this is a **repository-development doc: not packaged
into either Skill archive**, and no packaged Skill resource depends on it.
It reuses the shared review vocabulary (finding shape, P0/P1/P2 severity)
and the runner's result shape; it does not define a parallel review model
and it does not define quality metrics.

## Canonical invariant

> **A regression report joins a candidate run to a stored baseline run by case `id`, reports every per-case and aggregate delta between them, and calls out cases that got worse distinctly from cases that got better — without deciding whether a produced finding is *correct*, which is a quality metric (#41), and without ever writing the baseline itself.**

Every rule below is an elaboration of that sentence. Two concerns are
deliberately *out* of it and owned elsewhere (§10): scoring a run against
the fixtures' `expected` blocks (the expected-vs-produced match relation,
false-positive / false-negative accounting, precision/recall, aggregate
quality metrics — #41), and refreshing the baseline automatically (§8).

## 1. Terminology and ownership

- **Run result** — the full machine-readable output of one benchmark run:
  the ordered set of per-case results in the runner's shape
  ([`runner-contract.md`](runner-contract.md) §6), each carrying `id`,
  `input_kind`, `status`, and (when `status` is `executed`)
  `produced_findings` recorded verbatim.
- **Baseline artifact** — a run result stored as the reference point for
  future comparisons, plus the identifying metadata that makes a
  comparison meaningful (§2). It is produced by promoting a prior
  candidate run (§8); the report never creates or edits it.
- **Candidate run** — the run result under evaluation, produced now by the
  runner against the current Skill / adapter.
- **Regression report** — the machine-readable comparison this contract
  defines (§4–§7): the external evaluation artifact a human or a CI gate
  reads to decide whether a change is safe to merge.
- **Per-case delta** — the difference between a candidate case result and
  the baseline case result with the same `id` (§4).
- **Cross-run stability key** — the deliberately coarse, syntactic key
  used to decide whether a produced finding in the candidate corresponds
  to one in the baseline *for delta purposes only* (§4). It is **not** the
  #41 expected-vs-produced match relation and carries no correctness
  judgement; when it cannot decide, the report fails closed and surfaces
  the case for a human (§5).
- **Regression / improvement / mixed / unchanged** — the four per-case
  classifications (§5). "Regression" and "improvement" are reported as
  visibly distinct classes; "mixed" is surfaced with the regressions.

The report is **not** a Skill and is never packaged; no Skill launches it.
It is downstream evaluation infrastructure, exactly like the runner
([`runner-contract.md`](runner-contract.md) §1).

## 2. The baseline result artifact

The baseline artifact is a stored run result plus a small, closed
identity block:

| Field | Meaning |
|---|---|
| `results` | A run result: the list of per-case records in the runner's §6 shape, verbatim. |
| `corpus_id` | A stable digest of the corpus the run executed against (every fixture's `id` plus a content digest). Distinguishes "the reviewer changed" from "the corpus changed". |
| `adapter_id` | A caller-supplied identifier for the reviewer adapter / Skill revision the run used. |
| `created_at` | When the baseline was promoted. Informational only — never an input to any delta (§7). |

The artifact is a single serialized document (the same YAML/JSON the
runner already emits for `results`, wrapped with the identity block). It
lives wherever the caller keeps it — a committed file under version
control is the expected home so a baseline refresh is a reviewable diff
(§8) — but this contract fixes only its *shape*, not its storage location.

## 3. Inputs and the identity guard

A regression report takes exactly two inputs: a **baseline artifact** and
a **candidate run result** (with the same identity block computed for the
candidate).

- **Corpus identity must match.** If `corpus_id` differs between baseline
  and candidate, the report is a **report error** (§9): a delta computed
  across two different corpora is not a regression signal. The remedy is a
  deliberate baseline refresh (§8), not a silent comparison.
- **Adapter identity is recorded, not gated.** A differing `adapter_id`
  is expected — it is usually the whole point of the comparison — and is
  echoed into the report so the reader knows what changed.
- **Case sets are joined by `id`.** A case `id` present in the candidate
  but not the baseline is an **added case**; one present in the baseline
  but not the candidate is a **removed case**. Both are reported in their
  own sections and never silently dropped; neither is classified as a
  regression or improvement (there is nothing to compare), but a removed
  case is surfaced with the regressions for human attention.

## 4. Per-case comparison

For each case `id` present in **both** runs, the report computes a
per-case delta over exactly these dimensions, all read straight from the
runner's recorded output — never recomputed by re-running the reviewer:

1. **Execution status.** `baseline.status` vs `candidate.status`
   (`executed` / `error`, and the `error` reason when present).
2. **Produced-finding sets.** Using the cross-run stability key, the
   report partitions the candidate's `produced_findings` against the
   baseline's into:
   - **dropped** — in the baseline, absent from the candidate;
   - **gained** — in the candidate, absent from the baseline;
   - **retained** — present in both. Every retained finding is listed, each
     flagged with whether its severity changed between the runs.
3. **Severity histogram.** The per-severity counts (`P0` / `P1` / `P2`)
   of `produced_findings` in each run, and their difference.

The **cross-run stability key** is coarse and documented: a produced
finding is keyed by a normalized location built from the adapter's
**identity-bearing** location fields only — `location_intent`, `path` /
`file` (path-normalized), `symbol`, `anchor` — together with its stable
defect/claim discriminator when the adapter supplies one. Positional fields
(`line`/`col` and friends) are deliberately **excluded** — line numbers
drift as code moves, so a reviewer whose output shifts by a line still
pairs as *retained* rather than as a drop + gain. Severity is likewise
**not** part of the key — a finding that persists across runs at a
changed severity is a *retained* finding with a reported severity change,
not a simultaneous drop and gain. The key exists only to pair findings
across two runs of the *same* case for delta display. It deliberately
does **not**:

- decide whether a produced finding matches a fixture's `expected` spec
  (#41);
- compute precision, recall, or any pass rate (#41);
- merge or dedupe findings within a single run (the runner already
  recorded them verbatim — [`runner-contract.md`](runner-contract.md) §6).

When two findings cannot be confidently paired or separated by the key,
the case is reported as **mixed / ambiguous** and surfaced with the
regressions (§5) — the report never guesses in the reviewer's favor.

## 5. Regression vs improvement

Each compared case is placed in exactly one class, and the classes are
rendered as **visibly distinct groups** in the report (not a single
undifferentiated delta list):

| Class | Condition | Rendering |
|---|---|---|
| **regression** | `status` went `executed` → `error`; **or** the dropped set is non-empty and the gained set is empty; **or** a retained finding's severity rose in ordinal severity (`P2`→`P1`→`P0`) with nothing offsetting it. | Highlighted first, as the block that must be read. |
| **improvement** | `status` went `error` → `executed`; **or** the gained set is non-empty and the dropped set is empty; **or** a retained finding's severity fell with nothing offsetting it. | Reported in its own clearly separate block. |
| **mixed** | Both dropped and gained are non-empty, or the stability key was ambiguous (§4), or status and finding-set signals disagree. | Grouped **with the regressions** — fail closed; a human decides. |
| **unchanged** | Identical `status`, empty dropped and gained sets, identical severity histogram. | Collapsed to a count; listed by `id` only. |

The **Rendering** column describes the human-facing presentation of the
report. It is not a statement about the machine serialization: that always
emits the full per-case record (status, dropped, gained, retained with a
per-entry `severity_changed` flag, severity histogram) for **every** class,
`unchanged` included, so `totals` always reconcile against the per-case
detail (§6).

This classification is intentionally metric-free: it reports that the
reviewer's *observable output* for a case changed in a direction, not
whether that output is *right*. "The candidate stopped producing a
finding the baseline produced" is a regression signal worth a human's
attention regardless of whether that finding was ever correct — which is
exactly what a seeded-regression check needs, and is why scoring (#41) is
not a prerequisite for this report.

## 6. Aggregate report

Alongside the per-case sections, the report emits a corpus-level summary
computed only from the per-case classes and deltas above:

- **Counts per class** — how many cases are regressions, improvements,
  mixed, unchanged, added, removed.
- **Total dropped / gained / retained** produced findings across all
  compared cases.
- **Aggregate severity histogram delta** — baseline vs candidate
  `produced_findings` counts per severity, summed over all cases present
  in both runs (added and removed cases have no counterpart to difference).
- **`has_regressions`** — a single boolean: true iff the regression class
  or the mixed class or the removed-case set is non-empty. This is the
  flag a CI gate acts on; it is distinct from report process health (§9).

No aggregate here is a "score": there is no weighting, no pass rate, no
precision/recall. Those are #41 and are computed from the fixtures'
`expected` blocks, which this report never reads.

## 7. Deterministic, stable output

- **Byte-identical for identical inputs.** Given the same baseline
  artifact and the same candidate run result, the report serializes
  identically across machines and runs.
- **Deterministic ordering.** Cases are ordered by `id` within every
  section; produced findings within a delta are ordered by their
  cross-run stability key; classes appear in a fixed order
  (regressions, mixed, improvements, added, removed, unchanged).
- **No run-specific noise in the diff body.** `created_at`, wall-clock
  timing, temporary paths, and hostnames never appear in the comparison
  output; identity metadata (`corpus_id`, `adapter_id`) is echoed in a
  header, not mixed into per-case deltas.
- **Empty is a valid, stable report.** Two equal run results produce a
  well-formed report with every count zero and `has_regressions` false.

## 8. Baseline refresh is a deliberate, documented step

- The report **never** writes, promotes, or mutates the baseline
  artifact. It only reads the baseline and the candidate.
- Refreshing the baseline is an explicit human action: run the benchmark,
  read the regression report, and — only when the deltas are understood
  and accepted — promote the candidate run result to the new baseline
  artifact (recomputing its identity block) and commit that change as a
  reviewable diff.
- A corpus change (adding, removing, or editing a fixture) invalidates
  the `corpus_id` and therefore **requires** a baseline refresh in the
  same change set; §3's identity guard makes a stale baseline a hard
  error rather than a misleading comparison.
- There is no automatic promotion, no "update baseline on green", and no
  flag that makes the report write the baseline. Automating that decision
  is explicitly out of scope for #53.

## 9. Report status vs regression signal

- **Process health is separate from findings.** The report **fails**
  (non-zero process status) only when it cannot produce a trustworthy
  comparison: a baseline artifact that will not parse, a candidate run
  result that will not parse, or a `corpus_id` mismatch (§3).
- **Finding regressions is not a report failure.** A run that completes
  the comparison is a **successful report** even when
  `has_regressions` is true. Downstream (a CI gate, a human) decides what
  to do with `has_regressions`; that decision is not this contract's
  process exit status.
- This mirrors [`runner-contract.md`](runner-contract.md) §7: the runner's
  exit code reflects execution health, not review quality; the report's
  process status reflects comparison health, not whether the reviewer
  regressed.

## 10. Explicitly out of scope

| Not defined here | Owner |
|---|---|
| The expected-vs-produced match relation, false-positive / false-negative accounting, precision/recall, retrieval thresholds, aggregate quality metrics / scores | [#41](https://github.com/amirbena/code-review-skill/issues/41) |
| Executing the reviewer over the corpus, per-case isolation, the per-case result shape this report consumes | [`runner-contract.md`](runner-contract.md) / [#52](https://github.com/amirbena/code-review-skill/issues/52) |
| The fixture format and the corpus | [#50](https://github.com/amirbena/code-review-skill/issues/50) / [#51](https://github.com/amirbena/code-review-skill/issues/51) |
| Automatic baseline promotion / "update on green" | out of scope for [#53](https://github.com/amirbena/code-review-skill/issues/53) by its Non-Goals |
| CI wiring / scheduled execution / where the baseline file is stored | tracked on [#40](https://github.com/amirbena/code-review-skill/issues/40) |
| The P0/P1/P2 definitions and the decision derivation | [`../../shared/policies/severity.md`](../../shared/policies/severity.md) |
| The finding field shape | [`../../shared/templates/finding.md`](../../shared/templates/finding.md) |

## 11. On not being a scorer

The report is defined so that it needs **only** what the runner already
recorded — case `id`, `status`, and verbatim `produced_findings` — and
never the fixtures' `expected` blocks. That boundary is deliberate: a
regression report that stays purely a *run-to-run diff* can ship and be
useful (it catches a seeded regression the day it is introduced) before
the quality-metric layer (#41) exists, and it does not have to change
when #41 lands. If a later issue installs scoring, this report gains an
*optional* extra section keyed off #41's match verdicts; the run-to-run
diff defined here remains valid on its own.

## Status and canonical home

**This document is the authoritative contract** for benchmark regression
reporting until a later issue installs an equivalent runnable component in
a canonical home. At that point this document becomes the design record:
it MUST link to that component and MUST NOT keep evolving the reporting
behavior independently — exactly as
[`runner-contract.md`](runner-contract.md), "Status and canonical home,"
and [`fixture-format.md`](fixture-format.md), "Status and canonical home,"
describe for their own eventual installation.

The test-only reference report
[`../../tests/reference/benchmark_report.py`](../../tests/reference/benchmark_report.py)
mirrors this document for regression coverage (executed by
[`../../tests/unit/test_benchmark_report.py`](../../tests/unit/test_benchmark_report.py),
including the seeded-regression diff and the stable-output check). It is
not packaged and is not a Skill.
