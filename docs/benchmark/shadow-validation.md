# Shadow-Validating the Top-K Selector Against Full-Corpus Evidence

Repository-development contract for GitHub Issue
[#335](https://github.com/amirbena/code-review-skill/issues/335). Parent:
[#331](https://github.com/amirbena/code-review-skill/issues/331). Depends
on [`selection.md`](selection.md) (#334, the thing being validated — the
Top-K selection whose trustworthiness this document measures) and
[`drift-detection-and-regression-lifecycle.md`](drift-detection-and-regression-lifecycle.md)
(#332/#339, the broader-evidence comparison source this document consumes
and never re-derives). Canonical architecture:
[`../benchmark-measurement-architecture/benchmark-measurement-architecture-model.md`](../benchmark-measurement-architecture/benchmark-measurement-architecture-model.md)
§3 ("Pre-merge behavioral gating") and §5 ("PR benchmark path"); a genuine
contradiction between the two is resolved by updating the canonical design
through a reviewed change, never by redefining the architecture locally
here.

Like [`selection.md`](selection.md), this is a repository-development
doc: **not** packaged into either Skill archive, and no packaged Skill
resource depends on it.

## Canonical invariant

> **A selector that has never been checked against real, broader evidence is not trustworthy enough to inform a merge decision — even an informational one — no matter how principled its scoring looks on paper.**

## Revision note

This issue previously ended in "the actual transition to a required,
fail-closed merge gate." That end state is **not this architecture's
current direction**:
[`runtime-execution-contract.md`](runtime-execution-contract.md) §2.2/§4.3
establishes that Class 2 (maintainer-controlled) execution must never
become a contributor/merge prerequisite, and no Class 1 (provider-backed,
always-on CI) runtime exists or is being pursued. This document's scope is
therefore bounded to shadow-validation and an evidence-bar methodology
(§4); promotion to a required gate is recorded only as an explicitly
conditional, not-currently-pursued future step (§6).

## 1. Scope

This document owns:

- The **shadow-validation join** — what a "burn-in sample" is, and the
  case-level granularity it is evaluated at (§2).
- The **miss rate** — regressions the full corpus caught that a PR's
  Top-K selection, had it been the only signal, would have missed (§2).
- The **redundancy rate** — selected cases that never once correspond to
  an actually-observed regression across the burn-in window (§3).
- The **evidence-bar methodology** — how an acceptable miss rate /
  redundancy level gets decided from observed data, not guessed in
  advance (§4).
- The explicit statement that this deliverable's stopping point is the
  evidence bar itself, not a required-gate promotion (§6).

This document does **not** own (non-goals, mirroring the issue):

- The taxonomy, metadata, or index —
  [`taxonomy.md`](taxonomy.md) (#333).
- The relevance/coverage scoring formulas or the informational-mode
  workflow wiring that produces a PR's Top-K selection —
  [`selection.md`](selection.md) (#334). This document validates that
  existing wiring; it does not redesign it.
- Full-corpus or nightly execution itself —
  [`nightly-history-and-baseline.md`](nightly-history-and-baseline.md)
  (#332/#338)'s scope. This document is a consumer of its output only.
- Any change to #332's ownership, schedule, or drift-detection/issue-
  deduplication mechanics —
  [`drift-detection-and-regression-lifecycle.md`](drift-detection-and-regression-lifecycle.md)
  (#339). This document consumes #339's classified drift records; it
  never re-derives what counts as drift versus noise.
- Promoting any PR-time check to a required, contributor-blocking merge
  gate — not this architecture's current direction (§6); not implemented
  by this document.
- Provisioning or assuming a Class 1 (provider-backed, always-on CI)
  runtime — superseded ([#337](https://github.com/amirbena/code-review-skill/issues/337),
  revised by [#391](https://github.com/amirbena/code-review-skill/issues/391)),
  not reopened here.

The single source of truth for the comparison logic below is code, not
prose:
[`../../tests/reference/benchmark/benchmark_shadow_validation.py`](../../tests/reference/benchmark/benchmark_shadow_validation.py).
The sections here describe intent and rationale; consult the module for
the exact current computation.

## 2. The burn-in sample and the miss rate

A **burn-in sample** joins one PR's #334 Top-K explainability output to
the #339-classified nightly regression evidence for the burn-in window
that PR overlaps:

- `selected_case_ids` — the case ids from that PR's `selected_cases`
  entries ([`selection.md`](selection.md) §5).
- `regressed_case_ids` — the distinct case ids that had at least one
  #339 `DriftRecord`
  ([`drift-detection-and-regression-lifecycle.md`](drift-detection-and-regression-lifecycle.md)
  §2/§3) in the nightly comparison(s) that PR's burn-in window overlapped.

**This document never produces that join itself.** Deciding which nightly
comparison(s) a given PR's window overlaps, and assembling the sample from
#334's and #339's already-computed outputs, is external to this
contract — exactly as #334 and #339 are each external to one another. What
this document owns is what happens *once* a sample exists:
[`benchmark_shadow_validation.evaluate_sample`](../../tests/reference/benchmark/benchmark_shadow_validation.py)
splits a sample's regressed cases into **missed** (not in
`selected_case_ids` — the selection, had it been the only signal, would
not have caught this) and **caught** (present in both).

**Miss rate** is case-level, not finding-level: the selector
([`selection.md`](selection.md)) picks whole cases, not individual
expected-finding keys, so "would this selection have caught the
regression" is answered at the same granularity the thing being validated
actually operates at. Aggregated over every sample in a burn-in window
(`benchmark_shadow_validation.aggregate_burn_in`):

```text
miss_rate = total_missed_regressions / total_regressions_observed
```

A recurring real-world regression is counted fresh in every sample it
reappears in — the same regression showing up night after night is
correctly treated as repeated evidence the selector keeps missing it, not
collapsed into one event. This mirrors #339's own fingerprint carrying no
run-specific data while a "still reproducing" comment is posted every
night a regression recurs.

`miss_rate` is **`None`**, not `0`, when a window observed zero
regressions — a selector cannot be credited with a miss rate over evidence
that never existed. This mirrors
[`selection.md`](selection.md) §3.3's `insufficient-coverage` convention:
a vacuous case is reported as vacuous, never silently folded into a
passing number.

## 3. Redundancy / over-selection

**Redundancy is deliberately not defined as "zero marginal coverage gain
at pick time."**
[`selection.md`](selection.md) §4's stopping rule guarantees every case
the greedy algorithm picks has a strictly positive marginal Selection
Coverage gain at the moment it is picked — that internal signal can never
fire, by construction, so it cannot be reused here to mean "this case
turned out not to matter."

Instead, redundancy asks an empirical question over the whole burn-in
window: of every case the selector ever picked, how many **never once**
corresponded to an actually-caught regression?

```text
redundancy_rate = |cases selected at least once, never in caught_case_ids for any sample|
                   / |distinct cases selected at least once in the window|
```

A case is evaluated once per window regardless of how many samples it was
selected in — a case selected ten times and never once catching a real
regression is one redundant case, not ten. This is the "over-selection"
signal the issue's Scope describes: a case that scores well against
#333's taxonomy-coverage proxy but, against real burn-in evidence, is
carrying no defect-finding weight of its own.

`redundancy_rate` is **`None`** when nothing was ever selected in the
window — same vacuous-not-zero convention as §2.

A single sample's `unexercised_selected_case_ids` (a selected case with no
regression in *that one* comparison) is **not**, on its own, evidence of
redundancy — most selected cases are unexercised on most individual
nights by construction (most nights find no regression in most cases).
Redundancy is only a meaningful judgment once aggregated across the whole
window, never read off a single sample.

## 4. Evidence bar — a methodology, not a number

**This document does not assert an acceptable miss rate or redundancy
level.** The issue's own acceptance criteria require the bar to be "a
decision made from actual observed burn-in data, not asserted in
advance," and no live burn-in window exists yet — the Class 2 nightly
Routine target
([`cloud-routine-integration.md`](cloud-routine-integration.md),
[`nightly-history-and-baseline.md`](nightly-history-and-baseline.md)) is
maintainer-triggered, not yet accumulating a real schedule of paired
PR/nightly evidence. Hard-coding a threshold today would be exactly the
guessed-in-advance number the issue rejects.

Instead, this is the process a maintainer applies once real (or, per the
issue's own Validation section, reconstructed) burn-in evidence exists:

1. **Minimum window size before judging anything.** A burn-in report
   built from a handful of samples is noise, not signal —
   [`shadow-validation-burn-in-report.md`](shadow-validation-burn-in-report.md)'s
   worked example is explicitly a methodology demonstration, not an
   evidence-bar-setting data point, for exactly this reason. A maintainer
   should not draw a bar from a window smaller than the sample count
   needed for the observed rate to stop moving materially as new samples
   are added — a judgment call recorded alongside the bar decision, not a
   fixed constant this document invents.
2. **Read the report, not a single number in isolation.** §5's report
   object carries the full per-sample breakdown
   (`SampleEvaluation.as_dict()`) alongside the aggregate rates —
   `cases_never_caught_a_regression` names the specific cases driving a
   redundancy figure, and each sample's `missed_case_ids` names the
   specific regressions a miss-rate figure is built from. The bar decision
   should cite which cases/regressions it was informed by, not just the
   final fraction.
3. **Record the decision where the evidence lives.** The bar, once set, is
   recorded as an update to this document (§4), citing the burn-in report
   (or reports) it was derived from — not asserted in a PR description or
   left implicit in review comments.
4. **Revisit, don't fossilize.** #334's weights and thresholds are
   explicitly tunable ([`selection.md`](selection.md) §2); a bar set
   against one selector configuration is not assumed valid after that
   configuration changes. A maintainer who changes #334's scoring should
   treat the existing bar as provisional until re-validated against a
   fresh window.

No bar is currently recorded. Until one is, this document's deliverable
is the methodology above plus the worked report demonstrating it, per the
issue's own acceptance criteria.

## 5. Machine-readable report

One JSON object per burn-in window run, built by
`benchmark_shadow_validation.build_burn_in_report` and emitted by
[`../../scripts/benchmark/shadow_validate.py`](../../scripts/benchmark/shadow_validate.py),
optionally published to a GitHub Actions step summary via that script's
`--step-summary` option (the same convention
[`select_benchmark_cases.py`](selection.md) already uses). Fields:

- `window_description` — a human-readable description of the burn-in
  window this report covers (date range, sample count context).
- `sample_count` — the number of burn-in samples aggregated.
- `total_regressions` / `total_missed` / `miss_rate` — §2's figures;
  `miss_rate` is `null` when `total_regressions` is `0`.
- `distinct_selected_case_ids` / `cases_never_caught_a_regression` /
  `redundancy_rate` — §3's figures; `redundancy_rate` is `null` when
  `distinct_selected_case_ids` is empty.
- `per_sample` — one entry per burn-in sample: its `sample_id` and the
  `missed_case_ids` / `caught_case_ids` / `unexercised_selected_case_ids`
  split.

The report **never carries a pass/fail verdict**. It states the observed
figures only; applying §4's methodology to decide whether they clear a
bar is a maintainer act external to this tooling, exactly as
[`selection.md`](selection.md) ships `insufficient-coverage` as a
reported outcome without itself deciding whether that blocks anything.

## 6. Conditional / not currently pursued

Required-gate promotion — a PR-time benchmark check moving from
informational to a required branch-protection status check, fail-closed
on `runtime-unavailable`/`insufficient-coverage`, with an auditable
maintainer override — is **out of scope unless and until a future Class 1
(provider-backed, always-on CI) runtime is separately decided and built**.
It is not an assumed eventual step of this document, and it is not
blocked on anything this document does. The retired #255 PR-level
workflow (`benchmark-check.yml`, formerly the candidate for that eventual
promotion) no longer exists
([#420](https://github.com/amirbena/code-review-skill/issues/420)), and
under the current architecture there is no other GitHub Actions runtime
this deliverable is currently permitted to promote against — the selector
stays informational unless and until a future, separately-decided Class 1
runtime exists. If that runtime is ever built, promoting to a required
gate would be a separate, explicitly-scoped follow-up issue at that time,
reusing this document's evidence bar (§4) and methodology as its
precondition — not reopened here.

Nothing in this document's deliverable makes Class 2 (maintainer-
controlled) execution a prerequisite for a normal contributor PR to
merge.

## 7. Status and canonical home

This document is the authoritative contract for the shadow-validation
methodology, the miss-rate/redundancy-rate computation, and the
evidence-bar decision process until a later issue installs an equivalent
schema in another canonical home, exactly as
[`selection.md`](selection.md) describes for itself.
`tests/reference/benchmark/benchmark_shadow_validation.py` implements it;
`scripts/benchmark/shadow_validate.py` is the offline, GitHub-mutation-
free CLI that renders a burn-in window into the §5 report; the see
[`shadow-validation-burn-in-report.md`](shadow-validation-burn-in-report.md)
worked example satisfies the issue's Validation section with reconstructed
data. `tests/unit/benchmark/test_benchmark_shadow_validation.py` and
`tests/unit/benchmark/test_shadow_validate_cli.py` prove the miss-rate/
redundancy-rate arithmetic, the vacuous-not-zero convention, and that the
report never renders a verdict. It ships informational-only: no code path
described here fails a build, blocks a merge, or is added to branch
protection (§6). A conflict discovered later is resolved by updating this
document through a reviewed change, not by silently deviating in code.
