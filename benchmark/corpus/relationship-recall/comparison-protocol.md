# Search-Only vs. Relationship-Enriched Comparison: Protocol and Decision Rule

Repository-development artifact for GitHub Issue
[#605](https://github.com/amirbena/code-review-skill/issues/605) (R5 of epic
[#600](https://github.com/amirbena/code-review-skill/issues/600)). This file
is committed **before** the comparison is run, so the decision rule cannot be
fitted to the results. The results and the decision are recorded afterwards in
[`comparison.md`](comparison.md) and
[`comparison-observations.json`](comparison-observations.json).

## Question

Is a local, deterministic relationship index worth its complexity? More
discovered edges are not evidence of better reviews, so the only thing scored
is the **review outcome** on the [#602](README.md) corpus: correct finding,
correct no-finding, missed, or wrong.

## Arms

Both arms run the same packaged `local-code-review` Skill built from the
checkout under test, the same prompt, the same fixtures, and the same scorer.
Only one input differs.

| Arm | What the reviewer is given |
|---|---|
| **A: search-only** | Nothing extra. The `relationship-query` capability is not declared, so every relationship question runs the repository search fallback. |
| **B: enriched** | The host declares the `relationship-query` capability and supplies, per case, the answers an **ideal** provider would return, in the closed answer shape of the [capability contract](../../../docs/repository-intelligence/relationship-capability-contract.md), bound to the reviewed snapshot. |

Arm B is deliberately an **upper bound**. Its answers are authored from the
fixture's ground truth in [`relationship-answers.json`](relationship-answers.json),
cost nothing to build, are never stale, and never wrong. A real index can do no
better on recall and adds build cost, so:

- if the ideal provider does not clear the rule below, no real index can;
- if it does clear it, that is necessary, not sufficient. The spike (#606) must
  then show a real mechanism reaches that recall at acceptable build and runtime
  cost.

Arm B includes honest provider answers for the unresolvable cases: an
ambiguous-dispatch or external-input **candidate** and `complete: false`, never
a fabricated edge. Enrichment must not turn an unresolvable case into a finding.

## Run design

- Cases: the twelve cases of the [class map](README.md#relationship-classes)
  plus the second consumer positive. The cross-partition class stays not
  measurable.
- Repetitions: **2 per arm per case**, in independent workspaces. Outcomes are
  non-deterministic; a case is "correct" in a repetition, and rates are over
  case-repetitions.
- Scoring: the existing runner, matcher and metrics. No second validator.
- Skill binding: the Skill under test is the one packaged from this checkout,
  loaded through `--plugin-dir`, with the ambient installation disabled. Each
  repetition records the Skill invocation it actually made so a run that loaded
  another copy is excluded, not counted.
- Cost: wall-clock seconds, input/output/cache tokens and reported USD cost per
  review, from the CLI's own result event.
- Reproducibility: the harness, the answers file, the Skill-under-test version,
  the repository SHA and each fixture hash are recorded with the results.

## Measures

Computed per arm and per relationship class.

| Measure | Definition |
|---|---|
| Correct-conclusion rate | Share of case-repetitions with no false negative and no false positive. |
| Consumer / caller misses | False negatives on the consumer class. |
| Affected-test misses | False negatives on the affected-test class. |
| Placement errors | False negatives or false positives on the analogue class. |
| Interface misses | False negatives on the implementation/interface class. |
| Analogue consistency | Share of analogue cases with the same outcome in both repetitions. |
| Enabled findings | Case-repetitions correct in B whose same case was not correct in A. |
| False-positive growth | Total false positives in B minus A. |
| Inflation control | Findings B produces on control and unresolvable cases where A produces none. |
| Unresolved visibility | On unresolvable cases, the share of repetitions whose report renders the Context gaps disclosure. |
| Cost | Median and total seconds, tokens and USD per arm. |

## Decision rule

A local deterministic relationship index is **justified only if every
condition holds**. Any failure means *not justified*.

1. **Quality gain.** B has at least **3 more** correct case-repetitions than A,
   and the gain comes from at least **2 distinct cases**.
2. **No regression.** In no relationship class does B have fewer correct
   case-repetitions than A.
3. **No inflation.** B's false positives do not exceed A's, and the inflation
   control is zero.
4. **Acceptable cost.** B's median seconds and total tokens per review are each
   at most **1.5×** A's. Costs of building or running a real index are not
   measured here and belong to #606.
5. **Valid arms.** Every counted repetition invoked the Skill under test. If
   more than a quarter of repetitions in either arm are excluded or errored,
   the comparison is *inconclusive*, which is also not justified.

A tie, a gain below the threshold, or a gain concentrated in one case is not
evidence of a better review and does not justify an index. Finding more edges is
never a criterion.

## Reading the outcome

- **Not justified:** record what would change that. At minimum, a corpus whose
  relationships are not discoverable by reading the whole fixture, since a
  small fixture lets search-only see everything.
- **Justified:** name the #129 §11 deferrals it would reopen. A per-review,
  snapshot-bound index reopens the deferred "real, non-ephemeral index or
  language-specific static-analysis backend" and "any runtime that builds,
  persists, queries, or auto-attaches a repository graph during a review". It
  does not by itself reopen the deferred `influential_relationships` finding
  field or cross-repository context.
