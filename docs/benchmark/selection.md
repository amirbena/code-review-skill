# Deterministic Top-K Benchmark Selector with Weighted Coverage Policy

Repository-development contract for GitHub Issue
[#334](https://github.com/amirbena/code-review-skill/issues/334). Parent:
[#331](https://github.com/amirbena/code-review-skill/issues/331). Depends on
[`taxonomy.md`](taxonomy.md) (#333, candidate pool/taxonomy/index — inputs,
not produced here) and
[`runtime-execution-contract.md`](runtime-execution-contract.md) (#330,
the runtime the selected Top-K cases execute against). Blocks
[#335](https://github.com/amirbena/code-review-skill/issues/335), which
cannot validate or promote a selector that doesn't exist. Canonical
architecture:
[`../benchmark-measurement-architecture/benchmark-measurement-architecture-model.md`](../benchmark-measurement-architecture/benchmark-measurement-architecture-model.md)
§3 ("Bounded PR-time benchmark selection") and §5 ("PR benchmark path"); a
genuine contradiction between the two is resolved by updating the
canonical design through a reviewed change, never by redefining the
architecture locally here.

Like [`taxonomy.md`](taxonomy.md), this is a repository-development doc:
**not** packaged into either Skill archive, and no packaged Skill resource
depends on it.

## Canonical invariant

> **A selector that cannot explain, deterministically, why it picked what it picked is not trustworthy enough to inform a merge decision — even an informational one.**

Selection never scores or scans the whole corpus per PR ([#333](https://github.com/amirbena/code-review-skill/issues/333)'s
inverted index narrows first); the only model call anywhere in this path
is #333's one bounded PR-diff classification step. Everything downstream
of that — Case Relevance, Selection Coverage, and Top-K selection — is
pure, reproducible, unit-testable arithmetic over taxonomy tags: no
embeddings, no semantic search, no second model call.

## 1. Scope

This document owns:

- The **Case Relevance Score** and its policy bands (§2).
- The **Selection Coverage Score** — a distinct concept from relevance
  (§3).
- The greedy, bounded Top-K selection algorithm (§4).
- The explicit, non-silent `insufficient-coverage` outcome (§3.3).
- The machine-readable explainability object (§5).

This document does **not** own (non-goals, mirroring the issue):

- The taxonomy, corpus classification metadata, PR-diff classification
  model call, or the inverted index — [`taxonomy.md`](taxonomy.md) (#333).
- Actually executing any selected benchmark case — the runtime chain in
  [`runtime-execution-contract.md`](runtime-execution-contract.md) (#330).
- Whether/when this selector's output becomes a required, fail-closed
  merge gate, and any override mechanism —
  [#335](https://github.com/amirbena/code-review-skill/issues/335). This
  selector ships **informational-only**.

The single source of truth for every constant, weight, threshold, and
algorithm below is code, not prose:
[`../../tests/reference/benchmark/benchmark_selection.py`](../../tests/reference/benchmark/benchmark_selection.py).
The tables here describe intent and rationale; consult the module for the
exact current values.

## 2. Case Relevance Score

Deterministic, computed **only** over #333's candidate pool (the union of
inverted-index lookups for the PR's classified `(dimension, value)`
pairs) — never the full corpus. Per-dimension weighted overlap: a
dimension contributes its full weight to a candidate case's score when the
case's declared value(s) and the PR's classified value(s) share at least
one non-`unclassified` member; otherwise it contributes zero.

| Dimension | Weight |
| --- | --- |
| `capability` | 40 |
| `policy_contract` | 25 |
| `risk_mode` | 20 |
| `affected_surface` | 15 |

Weights sum to 100 and are tunable — a deliberate deployment/tuning knob,
not an architectural commitment of the canonical design (§5 of the
architecture model says so explicitly). `benchmark_selection.py` asserts
the sum and the dimension set stay in lockstep with
[`taxonomy.md`](taxonomy.md)'s four dimensions, so the two can never
silently diverge.

**Policy relevance bands:**

| Band | Score range | Meaning |
| --- | --- | --- |
| `primary` | `>= 60` | Strong candidate for the required set. |
| `secondary` | `40–59` | Supporting candidate — eligible for selection, not on its own sufficient to justify picking it over a stronger one. |
| `not-eligible` | `< 40` | Excluded from selection entirely, regardless of Top-K headroom. |

A case scoring below 40 is never selected, even if the Top-K bound has
unused headroom and coverage has not yet been reached — Case Relevance is
a hard eligibility filter, not merely a tiebreaker.

## 3. Selection Coverage Score

A **distinct concept** from Case Relevance: not "how relevant is this one
case" but "how much of the PR's weighted behavioral/risk surface does the
*selected set*, collectively, cover."

### 3.1 Implicated pairs

Every `(dimension, value)` pair the PR's classification implicated
receives a weight share: that dimension's weight (§2's table) divided
across however many non-`unclassified` values were implicated in that
dimension. When every dimension has at least one implicated value, these
shares sum to 100 across all implicated pairs. A dimension the PR-diff
classification left wholly `unclassified` contributes **no** pairs — it
cannot be "covered" by a selection when nothing was classified into it in
the first place. This deliberately **lowers the achievable coverage
denominator** rather than silently renormalizing the remaining
dimensions' weights up to fill the gap; a selector should never be able
to claim full coverage of a dimension it was never told anything about.

### 3.2 Coverage formula

A pair counts as **covered** once at least one selected case's taxonomy
metadata matches it (the case declares that dimension/value in its own
`metadata.taxonomy`).

```text
Selection Coverage = (sum of covered pairs' weight) / 100
```

### 3.3 Golden threshold and the `insufficient-coverage` outcome

**Golden threshold: Selection Coverage >= 60%.**

When greedy selection (§4) exhausts the Top-K bound or the eligible pool
without reaching 60%, the result is `insufficient-coverage` — a distinct,
explicit, non-silent outcome, **never** folded into a passing result. It
reports the achieved coverage and exactly which `(dimension, value)`
pairs remain uncovered. This document only produces that outcome; whether
it blocks a merge, and any override, is
[#335](https://github.com/amirbena/code-review-skill/issues/335)'s
decision — this selector ships informational-only (§1).

A PR whose classification implicated no pairs at all (every dimension
resolved `unclassified`) is a degenerate edge case, not
`insufficient-coverage`: there is nothing to cover, so
`benchmark_selection.select_cases` reports `sufficient-coverage` with an
empty selection rather than a spuriously failing 0% score.

## 4. Top-K selection algorithm

**Top-K bound** — configurable but hard-capped: `K_DEFAULT = 6`,
overridable per run within a fixed, non-configurable ceiling,
`K_MAX = 12`. Named constants in `benchmark_selection.py`, never a
workflow-YAML-buried magic number.

Selection proceeds **greedily** within the eligible (`>= 40`, i.e.
`primary` or `secondary` band) pool:

1. At each step, compute every remaining eligible case's **marginal
   coverage gain** — the sum of weights of currently-uncovered pairs that
   case's taxonomy matches.
2. Pick the case with the largest marginal gain. Ties are broken by
   higher Case Relevance Score, then — deterministically, so the same
   candidate pool and PR classification always yield the same selection —
   by the lexicographically first case id.
3. Stop when any of the following is first true:
   - The Top-K bound (§4) is reached.
   - 60% Selection Coverage (§3.3) is reached.
   - No remaining eligible case offers a positive marginal coverage
     gain — picking further would not move coverage at all.

This is a coverage-maximizing bounded selection, not a pure
highest-relevance-first selection: four highly relevant but redundant
cases exercising the same one capability are deliberately not preferred
over a lower-scoring case that closes an otherwise-uncovered
`(dimension, value)` pair — this is the mechanism that keeps a PR's
authorization/delegation dimension (for example) from going entirely
unexercised just because four correctness cases scored higher
individually.

## 5. Explainability

One machine-readable JSON object per run, built by
`benchmark_selection.build_explainability` and emitted by
[`../../scripts/benchmark/select_benchmark_cases.py`](../../scripts/benchmark/select_benchmark_cases.py),
published to the GitHub Actions step summary via that script's
`--step-summary` option (the same convention
`scripts/release/release_lib/cli.py` already uses). Fields:

- `resolved_taxonomy_classification` — the PR's resolved taxonomy
  classification (all four dimensions).
- `candidate_pool_size` — the candidate pool size after index narrowing.
- `selected_cases` — one entry per selected case, in pick order: its id,
  Case Relevance Score, band, matched taxonomy keys, and marginal
  coverage gain **at the moment it was picked** (not recomputed after
  later picks).
- `selection_coverage` — the final aggregate Selection Coverage.
- `coverage_threshold` — the configured threshold (§3.3).
- `top_k_bound` — the configured Top-K bound actually used for this run
  (§4).
- `uncovered_pairs` — every `(dimension, value)` pair left uncovered (empty
  on `sufficient-coverage`).
- `outcome` — `sufficient-coverage` or `insufficient-coverage` (§3.3).

## 6. Status and canonical home

This document is the authoritative contract for Case Relevance, Selection
Coverage, Top-K selection, and this selector's explainability output
until a later issue installs an equivalent schema in another canonical
home, exactly as [`taxonomy.md`](taxonomy.md) describes for itself. It
ships informational-only: no code path described here fails a build,
blocks a merge, or is added to branch protection — that is
[#335](https://github.com/amirbena/code-review-skill/issues/335)'s scope,
constrained by the architecture model's §4.1 Class 2 rule (maintainer-
controlled execution must never become a required contributor/merge
check).
