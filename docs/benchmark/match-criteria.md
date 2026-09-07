# Benchmark Finding Match Criteria

Repository-development contract for GitHub Issue
[#54](https://github.com/amirbena/code-review-skill/issues/54). It defines
**when a produced review finding is considered to match an expected
benchmark finding** — the dimensions the decision is made on, how an exact
match differs from a near-miss, and how the fixture format's
allowed-alternative constructs are resolved. It builds on the fixture
format ([`fixture-format.md`](fixture-format.md) §8–§9, #50) and is
consumed by the false-positive / false-negative metrics
([#55](https://github.com/amirbena/code-review-skill/issues/55)), the
severity-accuracy metric
([#56](https://github.com/amirbena/code-review-skill/issues/56)), and the
duplicate-noise metric
([#57](https://github.com/amirbena/code-review-skill/issues/57)). Parent
capability: [#41](https://github.com/amirbena/code-review-skill/issues/41).

Like [`fixture-format.md`](fixture-format.md) and the rest of
[`./`](README.md), this is a **repository-development doc: not packaged
into either Skill archive**, and no packaged Skill resource depends on it.
It reuses the shared finding shape and the `MATCH` / near-miss / `NO
MATCH` vocabulary and the two-axis matching discipline of
[`../findings/finding-matching-strategy.md`](../findings/finding-matching-strategy.md)
(the closed research of GitHub Issue
[#59](https://github.com/amirbena/code-review-skill/issues/59)); it does
**not** redefine that cross-revision identity relation and it does not
define a parallel review model.

## Canonical invariant

> **A produced finding MATCHES an expected benchmark finding only when it corresponds on both axes — the same defect, at the same location — judged by deterministic criteria over the fixture's structured fields. Corresponding on one axis while falling short on the other is a NEAR-MISS; anything else is NO-MATCH. This relation decides pairing only: it never counts findings, computes a score, or judges severity.**

Every rule below is an elaboration of that sentence. Three concerns are
deliberately *out* of it and owned elsewhere (§9): turning matches and
misses into counts / rates (#55), comparing the severity of a matched
finding against its expectation (#56), and clustering same-root-cause
findings into a noise measure (#57).

## 1. Terminology and ownership

- **Expected finding** — one entry the fixture author wrote under
  `expected.findings`: a single spec ([`fixture-format.md`](fixture-format.md)
  §8.1) or an `any_of` group (§8.4), each carrying a structured
  `location` (§8.3), a `claim`, an optional `defect_kind`, and an
  optional `alternatives` list.
- **Produced finding** — one reviewer result recorded verbatim by the
  runner ([`runner-contract.md`](runner-contract.md) §6): a severity, a
  location, a claim, and whatever additional descriptor fields the
  reviewer adapter supplied (`defect_kind`, `symbol`, `anchor`, line
  range).
- **Match axes** — the two independent correspondences a MATCH requires:
  **defect correspondence** (§4) and **location correspondence** (§3).
  Borrowed, not re-derived, from
  [`../findings/finding-matching-strategy.md`](../findings/finding-matching-strategy.md)'s
  "defect continuity + site continuity" discipline; neither axis can
  substitute for the other.
- **Pairwise result** — the three-valued outcome of comparing one
  produced finding to one expected spec: `MATCH`, `NEAR_MISS`,
  `NO_MATCH` (§5).
- **Entry outcome** — the best pairwise result achieved for a whole
  `expected.findings` entry once its `alternatives` / `any_of` members
  and `match: optional` flag are resolved (§6).

This document does **not** define: false-negative / false-positive
accounting, precision/recall, or any aggregate metric
([#55](https://github.com/amirbena/code-review-skill/issues/55));
severity-accuracy measurement for matched findings
([#56](https://github.com/amirbena/code-review-skill/issues/56));
duplicate / same-root-cause noise measurement
([#57](https://github.com/amirbena/code-review-skill/issues/57)); the
`findings_completeness` unexpected-finding rule
([`fixture-format.md`](fixture-format.md) §9 — its *accounting* is #55);
the cross-revision stable finding identity mechanism
([#42](https://github.com/amirbena/code-review-skill/issues/42), and its
research [#59](https://github.com/amirbena/code-review-skill/issues/59));
or how the runner captures produced findings
([#52](https://github.com/amirbena/code-review-skill/issues/52)).

## 2. The two match axes

A pairwise comparison evaluates **defect correspondence** (§4) and
**location correspondence** (§3) independently, then combines them (§5).
The axes are deliberately separate because the asymmetric error budget of
[`../findings/finding-matching-strategy.md`](../findings/finding-matching-strategy.md)
§1 applies here too: a false *split* (calling a real match a miss) is
visible and recoverable in a benchmark report; a false *merge* (crediting
the reviewer for a finding it did not make) silently inflates quality. So
a MATCH requires **both** axes to correspond, and a single strong axis
never carries a weak one.

Severity is **not** an axis. Two findings can MATCH while disagreeing on
severity; that disagreement is exactly what #56 measures over the matched
set. `severity` lists in a fixture (`fixture-format.md` §9 construct 4)
are also irrelevant to matching — they bound which severities are
*acceptable*, a #56 concern.

## 3. Location correspondence

Evaluated from the expected `location` (§8.3) against the produced
finding's location descriptor. Result is one of **EXACT**, **NEAR**,
**NONE**.

1. **`location_intent` gate.** When the expected intent is `repository`,
   location corresponds EXACT for any produced finding that is also
   repository-scoped or carries no single path, and NEAR otherwise. For
   every other intent the expected `path` is authoritative:
   - Produced finding has no resolvable path → **NONE** (it cannot be
     placed).
   - Normalized paths differ (`/`-separated, repository case rules, no
     leading `./`) → **NONE**. A finding in the wrong file is not the
     same finding.
2. **Same path — refine with the finer signals, in this order:**
   - Expected `symbol` present *and* produced `symbol` present *and* they
     are not the same qualified symbol (nor a documented rename of it) →
     **NEAR**.
   - Else expected `anchor` present *and* the post-image is available
     *and* the produced finding's reported line/range does not fall on or
     within the proximity window of a line whose post-image text contains
     `anchor` → **NEAR**.
   - Else expected `lines` present *and* produced line/range present
     *and* the ranges neither overlap nor sit within the proximity window
     → **NEAR**.
   - Else → **EXACT**.

   The **proximity window** is a fixed **± 3 lines**. It is the only line
   tolerance in this contract and does not vary between runs.
3. `lines` are **advisory** (`fixture-format.md` §8.3): a line delta
   alone, with `symbol` or `anchor` still corresponding, never drops
   EXACT to NEAR. Line numbers move; the anchor and the symbol are the
   durable hooks.

## 4. Defect correspondence

Evaluated from the expected `defect_kind` / `claim` against the produced
`defect_kind` / `claim`. Result is one of **CORRESPONDS**, **RELATED**,
**UNRELATED**.

1. **`defect_kind` decides when both sides have one.** Equal slugs →
   **CORRESPONDS**. Different slugs → **UNRELATED** — a distinct defect
   class, even at the same line, is a different finding. A missing
   `defect_kind` on either side is not a wildcard; fall through to the
   claim comparison.
2. **`claim` comparison** uses the `behavioral_claim` shape of
   [`../findings/finding-matching-strategy.md`](../findings/finding-matching-strategy.md)
   §2: a cause → faulty-behavior sentence. Each claim is reduced to a
   normalized content-token set — lower-cased, punctuation-split,
   stop-words and one/two-character tokens removed, identifiers, numbers,
   negation, and operators preserved. Correspondence is then measured
   deterministically by set containment and overlap:
   - One token set is a (non-empty) subset of the other, **or** their
     Jaccard overlap is **≥ 0.5** → **CORRESPONDS**.
   - Jaccard overlap is **≥ 0.25** (same mechanism described at different
     granularity) → **RELATED**.
   - Otherwise, or when a produced finding carries no assessable
     `defect_kind` *and* no `claim` → **UNRELATED**.
3. The two thresholds (0.5, 0.25) are fixed by this document and never
   tuned per run. No free-text or model judgement enters the decision: an
   LLM may *explain* a borderline pair for a human reading the benchmark
   report, but its opinion is never sufficient for a `CORRESPONDS`.

## 5. Combining the axes

| Location \ Defect | CORRESPONDS | RELATED | UNRELATED |
|---|---|---|---|
| **EXACT** | `MATCH` | `NEAR_MISS` | `NO_MATCH` |
| **NEAR** | `NEAR_MISS` | `NEAR_MISS` | `NO_MATCH` |
| **NONE** | `NO_MATCH` | `NO_MATCH` | `NO_MATCH` |

- **`MATCH`** — both axes correspond exactly. The reviewer found *this*
  defect *here*.
- **`NEAR_MISS`** — one axis corresponds and the other is close but not
  exact (right defect, adjacent/parent location; or right location,
  related-but-not-same defect). A near-miss is **not** a match: #55 counts
  it as a miss of the expected finding, but the benchmark report surfaces
  it distinctly so a human can see the reviewer was close.
- **`NO_MATCH`** — a disqualifying mismatch on either axis (wrong file,
  wrong defect class, unplaceable finding), or both axes weak.

The relation is **symmetric in inputs but not in roles**: it always
compares *one* produced finding to *one* expected spec. Pairing a whole
produced set to a whole expected set (one produced finding satisfies at
most one expected entry, and vice versa) is a resolution step owned by
#55, built on this pairwise relation.

## 6. Allowed alternatives and optionality

The fixture format's four variance constructs
([`fixture-format.md`](fixture-format.md) §9) resolve into the entry
outcome as follows:

- **`alternatives` (construct 1).** The entry's acceptable sub-specs are
  `{primary} ∪ {primary with each alternative's narrowed
  location/claim/defect_kind substituted in}`. A produced finding's
  result against the entry is the **best** (`MATCH` > `NEAR_MISS` >
  `NO_MATCH`) it achieves against any one sub-spec. `alternatives` never
  makes the entry optional.
- **`any_of` group (construct 2).** Each member is a full spec (§8.4).
  The entry outcome is the best pairwise result across all members, and
  the report records **which** member produced it. "Exactly one member
  satisfied" is a #55 pairing/accounting rule, not part of this
  relation.
- **`match: optional` (construct 3).** The pairwise result is computed
  identically. Optionality changes only downstream accounting: a produced
  finding that `MATCH`es an optional entry is **not** a false positive,
  and an optional entry with no `MATCH` is **not** a missed finding
  (#55).
- **`severity` list (construct 4).** Ignored here entirely — matching is
  severity-independent (§2); the list is a #56 input.

An entry outcome therefore carries: the best `MATCH` / `NEAR_MISS` /
`NO_MATCH`, the produced finding that achieved it, the satisfying
sub-spec or `any_of` member, and whether the entry was `required`.

## 7. Determinism and two-reader consistency

- **Fixed evaluation order.** Location axis then defect axis then the §5
  table; within each axis the numbered steps above are applied in order
  and the first that fires decides. No step is skipped or reordered based
  on the other axis's result.
- **No scores.** There is no weighted confidence total and no verdict
  that changes between runs. The only tolerances are the fixed ± 3-line
  proximity window (§3) and the two fixed claim-overlap thresholds
  (0.5 / 0.25, §4) — all three stated in this document, none tunable, and
  the token overlap is exact rational arithmetic, not a
  platform-dependent float.
- **Ties resolve deterministically.** When several produced findings tie
  for an entry's best result, the earliest one wins — the lowest index in
  the runner's ordered `produced_findings` list ([`runner-contract.md`](runner-contract.md)
  §6); when several expected sub-specs or `any_of` members tie, the
  primary (or the first member in document order) wins, then
  `alternatives` in document order.
- **Two readers, same verdict.** The worked examples (§8) are the
  conformance bar: two people applying §3–§6 to them must reach the same
  `MATCH` / `NEAR_MISS` / `NO_MATCH` for every row.

## 8. Worked examples

Each row compares **one** produced finding to **one** expected spec. All
six are encoded verbatim as data-driven cases in
[`../../tests/unit/test_benchmark_match.py`](../../tests/unit/test_benchmark_match.py);
two readers applying §3–§6 must reach the `Result` column for every row.

| # | Expected `location` / `claim` / `defect_kind` | Produced `location` / `claim` / `defect_kind` | Location | Defect | Result |
|---|---|---|---|---|---|
| 1 | `auth/login.py` lines 40–40, symbol `authenticate`; "unsanitized name reaches a shell true command injection"; `command-injection` | `auth/login.py` line 41, symbol `authenticate`; —; `command-injection` | EXACT — same path + symbol, 1-line drift is within the window | CORRESPONDS — equal `defect_kind` | **`MATCH`** |
| 2 | as #1 | `auth/login.py` line 40; "unsanitized name reaches a shell true command"; *(no `defect_kind`)* | EXACT — same path + line, no conflicting finer signal | CORRESPONDS — produced claim tokens ⊆ expected claim tokens | **`MATCH`** |
| 3 | as #1 | `auth/session.py` line 12; —; `command-injection` | NONE — different path | CORRESPONDS | **`NO_MATCH`** |
| 4 | as #1 | `auth/login.py`, symbol `build_login_command`; —; `command-injection` | NEAR — same path, different symbol, no rename | CORRESPONDS | **`NEAR_MISS`** |
| 5 | `report/export.py` line 88; "user controlled export path escapes the export directory path traversal"; `path-traversal` | `report/export.py` line 88; "export path argument is not validated"; `missing-input-validation` | EXACT | UNRELATED — contradictory `defect_kind` slugs | **`NO_MATCH`** |
| 6 | `pagination.py` line 15; "slice end off by one page repeats one row from the next page"; *(no `defect_kind`)* | `pagination.py` line 15; "off by one in pagination page bounds"; *(no `defect_kind`)* | EXACT | RELATED — token overlap ≥ 0.25 and < 0.5 | **`NEAR_MISS`** |

**Row 5, entry outcome.** The fixture author encodes "either
`path-traversal` or `missing-input-validation` is a correct read of this
code" as an `any_of` group (§6). Row 5 is `NO_MATCH` against the
*`path-traversal` member*; against the *`missing-input-validation`
member* of the same group the identical produced finding is a `MATCH`, so
the **entry outcome** is `MATCH`.

## 9. Explicitly out of scope

| Not defined here | Owner |
|---|---|
| False-negative / false-positive counts, precision/recall, per-case and aggregate quality metrics, the produced↔expected set-pairing resolution | [#55](https://github.com/amirbena/code-review-skill/issues/55) |
| Severity accuracy over the matched set (over- vs under-severity, exact-match rate) | [#56](https://github.com/amirbena/code-review-skill/issues/56) |
| Duplicate / same-root-cause clustering and the noise metric | [#57](https://github.com/amirbena/code-review-skill/issues/57) |
| A single blended quality score or a merge gate | out of scope for [#41](https://github.com/amirbena/code-review-skill/issues/41) by its Non-Goals |
| The cross-revision stable finding identity mechanism (produced-vs-earlier-produced) | [#42](https://github.com/amirbena/code-review-skill/issues/42) / [#59](https://github.com/amirbena/code-review-skill/issues/59) |
| The fixture format (`location`, `claim`, `defect_kind`, variance constructs) and the corpus | [#50](https://github.com/amirbena/code-review-skill/issues/50) / [#51](https://github.com/amirbena/code-review-skill/issues/51) |
| Capturing produced findings; the per-case result shape | [#52](https://github.com/amirbena/code-review-skill/issues/52) |
| The P0/P1/P2 definitions | [`../../shared/policies/severity.md`](../../shared/policies/severity.md) |
| The finding field shape | [`../../shared/templates/finding.md`](../../shared/templates/finding.md) |

## Status and canonical home

**This document is the authoritative contract** for the benchmark
expected-vs-produced match relation until a later issue installs an
equivalent runnable component in a canonical home. At that point this
document becomes the design record: it MUST link to that component and
MUST NOT keep evolving the criteria independently — exactly as
[`fixture-format.md`](fixture-format.md), "Status and canonical home,"
and [`runner-contract.md`](runner-contract.md), "Status and canonical
home," describe for their own eventual installation.

The test-only reference matcher
[`../../tests/reference/benchmark_match.py`](../../tests/reference/benchmark_match.py)
mirrors this document for regression coverage (executed by
[`../../tests/unit/test_benchmark_match.py`](../../tests/unit/test_benchmark_match.py),
including every §8 worked example as a data-driven case). It is not
packaged and is not a Skill.
