# Benchmark Citation-Existence Check

Repository-development contract for GitHub Issue
[#349](https://github.com/amirbena/code-review-skill/issues/349). It defines
**how a benchmark run mechanically checks that the location and evidence a
produced finding cites actually exist in the reviewed tree** — a fabricated
file, an out-of-range line, an absent symbol, or a quoted snippet that is
not there — per case and in aggregate, as a metric category **separate from**
the match / near-miss / no-match outcomes. Canonical design:
[`../../docs/benchmark-measurement-architecture/benchmark-measurement-architecture-model.md`](../../docs/benchmark-measurement-architecture/benchmark-measurement-architecture-model.md),
§12.3. It builds on the per-case result shape
([`runner-contract.md`](runner-contract.md) §6, #52) and on the
claim/location extraction
[#342](https://github.com/amirbena/code-review-skill/issues/342) restored in
the production adapter; it sits beside the #41 quality metrics
([#55](https://github.com/amirbena/code-review-skill/issues/55),
[#56](https://github.com/amirbena/code-review-skill/issues/56),
[#57](https://github.com/amirbena/code-review-skill/issues/57)).

Like [`duplicate-noise.md`](duplicate-noise.md) and the rest of
[`./`](README.md), this is a **repository-development doc: not packaged
into either Skill archive**, and no packaged Skill resource depends on it.
It adds no runtime gate, changes no review's findings or decision, and does
not touch the matcher's fixture correspondence
([`match-criteria.md`](match-criteria.md), unchanged).

## Canonical invariant

> **A benchmark run's citation fidelity is, per produced finding, one of three statuses — `verified`, `fabricated`, or `unverifiable` — decided only from the produced finding's own cited path, line span, symbol, and quoted evidence against the text of the files in the reviewed tree that the runner captured before cleanup: a finding is `fabricated` exactly when a check that could be run positively fails (the file is not in the tree, the line span is outside the file, the symbol is absent, or none of its quoted evidence is present near the cited location), `unverifiable` when nothing could be checked or existence could not be decided, and `verified` otherwise. The check proves existence only — never that the citation was inspected — and no expected finding, no match result, no severity, and no confidence enters it.**

Every rule below elaborates that sentence. The two conservative defaults —
"a check that *could not run* is never a failure" and "any one present quote
is enough" — exist so a genuine finding is never flagged: the signal is
useful only if `fabricated` is nearly always a real fabrication.

## 1. Terminology and ownership

- **Reviewed tree** — the disposable workspace the runner materialized for a
  case after any `input.patch` is applied (for a `repo_ref` case: the
  checked-out `commit`). It is the tree the reviewer saw.
- **Cited path / line span / symbol** — the finding's structured `location`
  fields (`path`, `line` or `lines`, `symbol`), read through the same
  normalizer the matcher uses (`Descriptor.from_produced`); the path is
  normalized by the runner's `cited_path` (`\` → `/`, leading `./` dropped).
- **Evidence quotes** — the backticked spans in the finding's `Evidence`
  value, carried by the production adapter into
  `ProducedFinding.extra["evidence_quotes"]` (§4).
- **`verified` / `fabricated` / `unverifiable`** — the three statuses (§3).
- **Fabrication rate** — `fabricated / (verified + fabricated)` as an exact
  reduced fraction, `null` when nothing was checkable.

This document does **not** define the match relation (#54), pairing or
miss/incorrect counts (#55), severity accuracy (#56), duplicate noise (#57),
provenance / citation *grounding* (whether the citation was inspected — the
deferred cross-check of design §12.2), or any decision derivation.

## 2. Capturing the reviewed tree

The workspace is deleted when the case ends, so the runner reads the files a
finding cites **inside the case, after the reviewer returns and before
cleanup**, into `CaseResult.cited_sources`: a mapping from each distinct
cited path to the file's text, or to `null` when that path is not a regular
file *of the workspace*. Like `post_image` it is deliberately absent from the
stable machine-readable case shape ([`runner-contract.md`](runner-contract.md)
§6).

- **Containment.** Only files inside the workspace are read. An absolute
  path, a `..` escape, or a symlink leaving the workspace is not a file of
  the reviewed tree: it maps to `null` and is never read.
- **Undecidable is not missing.** A file that cannot be read as UTF-8, is
  larger than `MAX_CITED_FILE_BYTES` (1,000,000), or falls past the
  `MAX_CITED_PATHS` (50) distinct-path cap is **left out of the mapping** —
  existence is then undecidable (§3), never `null`.
- **Best-effort.** A capture failure never fails the case.

## 3. The per-finding check

Statuses are decided in this order:

1. **No cited path** (repository-scoped / pathless / non-structured
   location, or a path that still contains `:` — an unparsed
   `path:locator`, which is not a file), or the cited path is **absent from
   `cited_sources`** → `unverifiable`.
2. The path maps to `null` → `fabricated` with reason `file-missing` (no
   further check runs).
3. Otherwise the file exists, and each check below adds its reason when it
   fails, reported in this fixed order:

| Reason | Fails when |
|---|---|
| `line-out-of-range` | a cited line span is not `1 ≤ start ≤ end ≤ line_count` |
| `symbol-absent` | the cited symbol is an identifier (optionally `A.b`, `A::b`, `A#b`, `f()`) whose last component does not occur as a whole word in the file; a prose "narrow section" symbol is **never** checked |
| `snippet-absent` | the finding has quotable evidence quotes (§4) and **none** is present in the search window |

`fabricated` iff at least one reason was added; `verified` when the check ran
and added none. Nothing the check does depends on whether the finding
`MATCH`es a fixture.

## 4. Quote rules and fixed tolerances

- **Quotable.** An evidence quote counts only if it has at least
  `MIN_QUOTE_CHARS` (6) non-whitespace characters and is not a `path:line`
  locator (ends in `:<n>` or `:<n>-<n>`) — those are references, not quoted
  code.
- **Search window.** With an in-range cited line span: the span plus
  `SNIPPET_WINDOW_LINES` (10) lines on each side. With only a path or symbol,
  or after `line-out-of-range`: the whole file.
- **Present** = the quote, whitespace removed, is a substring of the window,
  whitespace removed; **else** at least `SNIPPET_TOKEN_COVERAGE` (3/4, an
  exact `Fraction`) of the quote's word tokens are matched **in order**
  (longest common subsequence) within one segment of consecutive window
  lines as long as the quote has lines — so reordered or scattered
  identifiers that merely occur somewhere nearby do not count.
- **Any one present quote suffices**; the finding is `snippet-absent` only
  when none is.

These are the only tolerances. They are documented limits, not a claim of
completeness: a near-copy that changes at most a quarter of a real line's tokens
still passes, a fabrication whose quoted text happens to exist is not
caught (the deferred grounding question), and a finding that quotes only
code from a *different* file than it cites can be flagged.

## 5. Per-case and aggregate output

Per case: `id`, `status` (`executed` / `errored`), `produced`, `verified`,
`fabricated`, `unverifiable`, `fabrication_rate`, and `fabricated_findings` —
one `{index, path, reasons}` record per fabricated finding. An errored case
(or one with no result) produced nothing: all zero, `status: errored`,
`fabrication_rate: null`. Aggregate: `total_produced`, `total_verified`,
`total_fabricated`, `total_unverifiable`, `cases_with_fabricated_citations`,
and one `fabrication_rate` — plain sums, no weighting, no score.

## 6. Rendering and wiring

The production entrypoint
[`scripts/run_benchmark.py`](scripts/run_benchmark.py) emits the result as a
top-level `citation_fidelity` key **beside** `metrics`, never inside it and
never merged into a match outcome. The reference module also exposes a
`citation_fidelity_section(candidate, baseline=)` mirroring the #55–#57
sections (candidate alone, or per-case and aggregate `fabricated` deltas plus
the rate). Neither ever changes `has_regressions`, a run's exit code, a
finding's severity or confidence, or a decision. It is benchmark evidence
only — no runtime gate on live reviews (design §12.1).

## 7. Worked examples

Encoded verbatim as data-driven cases in
[`../../tests/unit/benchmark/test_benchmark_citation.py`](../../tests/unit/benchmark/test_benchmark_citation.py);
two readers applying §3–§4 must reach the status and reasons for every row.
The captured file `a.py` has 42 lines: `line 1` … `line 40`, then
`def target(x):` (41) and `    return x + 1` (42).

| # | Produced finding | Status | Reasons |
|---|---|---|---|
| 1 | `a.py:42`, quote `return x + 1` | `verified` | — |
| 2 | `gone.py:1` (not in the tree) | `fabricated` | `file-missing` |
| 3 | `a.py:500` | `fabricated` | `line-out-of-range` |
| 4 | `a.py`, symbol `missing_fn` | `fabricated` | `symbol-absent` |
| 5 | `a.py:42`, quote `os.system(cmd)` | `fabricated` | `snippet-absent` |
| 6 | `a.py:1`, quote `return x + 1` (line 42 is outside the ± 10 window) | `fabricated` | `snippet-absent` |
| 7 | `a.py:42`, only quote `a.py:42` (a locator) | `verified` | — |
| 8 | `a.py`, symbol `the setup section` (prose) | `verified` | — |
| 9 | repository-scoped, no path | `unverifiable` | — |
| 10 | `big.py:1`, file too large to capture | `unverifiable` | — |
| 11 | `a.py:500`, symbol `missing_fn`, quote `os.system(cmd)` | `fabricated` | `line-out-of-range`, `symbol-absent`, `snippet-absent` |
| 12 | `a.py:42`, quote `x + return 1` (the tokens of line 42, out of order) | `fabricated` | `snippet-absent` |
| 13 | `a.py:L42-L43`, unparsed (path still contains `:`) | `unverifiable` | — |

Rows 2–6, 11, and 12 are the fabrication the acceptance criteria ask to be
flagged; rows 7–10 and 13 are the deliberate non-flags a looser rule would raise.

## 8. Explicitly out of scope

| Not defined here | Owner |
|---|---|
| Whether a citation was actually *inspected* (provenance / citation grounding) | design §12.2 — [#348](https://github.com/amirbena/code-review-skill/issues/348) and the deferred cross-check |
| The produced-vs-expected match relation | [#54](https://github.com/amirbena/code-review-skill/issues/54) — [`match-criteria.md`](match-criteria.md) |
| Missed / incorrect counts | [#55](https://github.com/amirbena/code-review-skill/issues/55) — [`missed-and-incorrect-findings.md`](missed-and-incorrect-findings.md) |
| Severity accuracy | [#56](https://github.com/amirbena/code-review-skill/issues/56) — [`severity-accuracy.md`](severity-accuracy.md) |
| Duplicate noise | [#57](https://github.com/amirbena/code-review-skill/issues/57) — [`duplicate-noise.md`](duplicate-noise.md) |
| Carrying claim / location into the harness | [#342](https://github.com/amirbena/code-review-skill/issues/342) |
| A runtime gate on live reviews, or a merge gate on this metric | not defined; benchmark signal only (design §12.1) |
| The finding field shape | [`../../shared/templates/finding.md`](../../shared/templates/finding.md) |

## Status and canonical home

**This document is the authoritative contract** for the benchmark
citation-existence check until a later issue installs an equivalent runnable
component in a canonical home; it then becomes the design record, exactly as
[`duplicate-noise.md`](duplicate-noise.md), "Status and canonical home,"
describes.

The test-only reference
[`reference/benchmark_citation.py`](reference/benchmark_citation.py)
mirrors this document (executed by
[`../../tests/unit/benchmark/test_benchmark_citation.py`](../../tests/unit/benchmark/test_benchmark_citation.py),
including every §7 worked example). The runner's capture is
[`reference/benchmark_runner.py`](reference/benchmark_runner.py)
(`CaseResult.cited_sources`); the quote extraction is
[`scripts/benchmark_review_adapter.py`](scripts/benchmark_review_adapter.py).
Nothing here is packaged and none of it is a Skill.
