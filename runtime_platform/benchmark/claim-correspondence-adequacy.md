# Claim-Correspondence Matcher Adequacy — Research Recommendation

Repository-development research for GitHub Issue
[#343](https://github.com/amirbena/code-review-skill/issues/343). Answers,
with real harness-fidelity-corrected benchmark runs (after
[#342](https://github.com/amirbena/code-review-skill/issues/342) landed),
whether [`match-criteria.md`](match-criteria.md)'s (#54) lexical
Jaccard/subset claim-correspondence check can reliably recognize an
independently-phrased-but-correct finding. It recommends, without
implementing, the smallest deterministic contract change that would close
the observed gap.

This document is a research record, like
[`../../docs/findings/finding-matching-strategy.md`](../../docs/findings/finding-matching-strategy.md)
(#59). It does not redefine `match-criteria.md`'s contract; any redesign it
recommends is a proposal for a subsequent reviewed change to that document,
per #343's own scope.

---

## Decision

**Deterministic matcher redesign is justified**, and the guardrail's
preference order (#343: exhaust deterministic options before an LLM/semantic
judge) already identifies the right first move: **defect-identity
correspondence (`defect_kind`)**, `match-criteria.md` §4.1 — not a new
mechanism, an *existing, already-specified* one that the production path
never actually exercises, because the packaged `local-code-review` finding
rendering never emits a machine-readable `defect_kind` on the produced side.
Every real finding this study captured — including three that are
unambiguously, manually `SEMANTICALLY_EQUIVALENT` to their fixture's expected
defect — fell through §4.1 for lack of a produced `defect_kind` and was
decided entirely by free-text claim-token Jaccard, which then classified all
three as `UNRELATED` (`NO_MATCH`).

This is **not** a #342 residual defect: location correspondence (anchor +
symbol/line proximity) worked correctly in every case that had an anchor,
confirming #342's fidelity fix reached the matcher as designed. The gap is
specific to the defect/claim axis, and specifically to `defect_kind` never
being populated in practice — the current lexical claim comparison is a
fallback path that #343's own guardrail already ranks last, being exercised
as if it were the primary signal.

Recommended next step (a **follow-up implementation issue, not this one**):
evaluate populating a real `defect_kind` on produced findings (requiring the
packaged rendering to emit a stable defect-class slug) before evaluating
options 2–4. Do not conclude this is sufficient without that trial — see
"Open question: slug vocabulary stability" below, which is exactly the kind
of design question a follow-up issue must resolve.

---

## 1. Method

Reran the exact three corpus cases #342's own investigation named as its
motivating, non-trivial cases —
[`correctness-off-by-one-pagination`](../../docs/benchmark/corpus/correctness-off-by-one-pagination.yaml),
[`quality-duplicated-branch-logic`](../../docs/benchmark/corpus/quality-duplicated-branch-logic.yaml),
[`security-command-injection`](../../docs/benchmark/corpus/security-command-injection.yaml) — as
the representative sample (#343 scope explicitly permits "a representative
corpus/sample ... or a defined representative subset"; these three are the
only non-trivial, non-clean corpus cases and are the cases the open question
was raised against).

Each case was run through the **real, unmodified production path**:

```text
python3 runtime_platform/benchmark/scripts/run_benchmark.py --case-id <id> --cli claude
```

— `ProductionReviewerAdapter` invoking the real `claude` CLI against the
packaged `local-code-review` Skill in an isolated per-case workspace, through
the existing runner/matcher/metrics contracts (#52/#54/#55) exactly as a
developer or CI would run them. No hand-replayed workaround, no stub
adapter, no matcher call constructed manually.

**Runtime/CLI/model metadata:**

- Repository HEAD: `40061f1ffc829113c82facbb8803ba4c7ae2d0a3` (main, includes
  #342's merge, PR [#347](https://github.com/amirbena/code-review-skill/pull/347))
- Review CLI: `claude` (Claude Code) version `2.1.272`
- Run date: 2026-09-15 (UTC)
- Corpus dir: `docs/benchmark/corpus` (unmodified)
- `correctness-off-by-one-pagination` was run **twice** through the full
  production path (Runs A and B below) to observe run-to-run
  reviewer-verbosity variance (the CLI is not deterministic); the other two
  cases were run once each. Four production-path runs total (§2's table),
  zero adapter/runtime errors. A fifth, off-pipeline invocation of the same
  `correctness-off-by-one-pagination` input — the adapter's own prompt and
  CLI invocation, run directly and its raw stdout captured without going
  through the matcher/metrics — was used only to confirm that Run A's thin
  claim (§3) reflects genuine CLI output variance and not a parsing defect;
  it produced its own, differently-worded rich `Evidence` block (distinct
  from Run B's), consistent with §7's observation below. It is not counted
  among, or scored against, the four production-path runs.

## 2. Raw results

| Run | Case | produced severity | produced location | false_negatives | false_positives | near_misses |
| --- | --- | --- | --- | --- | --- | --- |
| A | `correctness-off-by-one-pagination` (1st) | P0 | `app/pagination.py:3` | 1 | 1 | 0 |
| B | `correctness-off-by-one-pagination` (2nd) | P1 | `app/pagination.py:3` | 1 | 1 | 0 |
| C | `security-command-injection` | P0 | `app/backup.py:5-6` | 1 | 1 | 0 |
| D | `quality-duplicated-branch-logic` | P2 | `app/notify.py:3-7` | 1 | 1 | 0 |

**Every one of the four runs scored `NO_MATCH`: 0 `MATCH`, 0 `NEAR_MISS`,
4/4 both a false negative and a false positive**, despite the reviewer
correctly identifying the seeded defect, at a location the location axis
accepted, in every run (confirmed manually below). This is the identical
symptom #342 originally reported pre-fix (3 false negatives, 3 false
positives, 0 near-misses) — now reproduced **after** the fidelity fix, on
runs that do carry full Evidence content to the matcher, which isolates the
remaining gap to the claim/defect axis rather than to harness fidelity.

### Location axis: worked correctly in every run

All three cases have an `anchor` in their expected `location`. Checked
against each run's produced `location` and the case's post-patch file
content:

- Run A/B: anchor `"offset + page_size + 1"` is on post-patch line 3;
  produced `line: 3` — within the ±3-line window → **EXACT**.
- Run C: anchors `"subprocess.run(cmd, shell=True"` (line 6) and
  `"f\"tar -czf {name}.tar.gz data/\""` (line 5, `alternatives`); produced
  `lines: {5, 6}` — overlaps both → **EXACT**.
- Run D: anchor `"elif kind == \"sms\":"` (line 4 of the post-patch file,
  inside the `notify` symbol); produced `lines: {3, 7}` — overlaps the
  anchor line and the enclosing symbol range → **EXACT**.

Combined with §5 of `match-criteria.md` (EXACT + UNRELATED → `NO_MATCH`),
every run's `NO_MATCH` is attributable entirely to the **defect axis**
scoring `UNRELATED`, not to location.

## 3. Manual adjudication (defect axis)

Per #343's adjudication instruction, each produced claim was compared
against its expected `claim` and judged against the finding-quality
contract ([`../../shared/templates/finding.md`](../../shared/templates/finding.md)):
same root defect, clear consequence, understandable without the fixture, no
missing causal detail.

### Run A — under-specified reviewer output (genuine reviewer variance, not a matcher gap)

- Produced claim (title only; no `Evidence`/`Impact`/`Details` bullet
  rendered in that particular CLI invocation): *"Off-by-one error returns
  `page_size + 1` items per page"*.
- Manual judgment: **`SEMANTICALLY_EQUIVALENT`, but minimal** — correct
  defect, correct consequence, but the reviewer's own rendered output that
  run genuinely carried no `Evidence`/`Impact` content for `_build_claim` to
  append. This is not a parsing gap: the off-pipeline raw-stdout probe
  described in §1 — the same case, same input, same adapter prompt and
  CLI invocation, captured before parsing — confirms `parse_review_output`
  correctly carries an `Evidence` bullet through to the claim when the CLI
  renders one (it did, richly, on that probe invocation); Run A's CLI
  output that particular run just did not render one. The CLI itself
  renders `Evidence` inconsistently run to run, per §7. This is
  reviewer-output variance across runs, not a #342 harness regression and
  not evidence about the matcher's adequacy on well-evidenced claims —
  bucketed separately from Runs B–D below.

### Run B — lexical matcher false negative

- Produced claim (title + `Evidence`, verbatim from the real CLI run):
  > `page()` returns `page_size + 1` items instead of `page_size` `end` is
  > computed as `offset + page_size + 1` and used directly as the slice's
  > upper bound (`items[offset:end]`). Since Python slicing
  > `items[offset:end]` is already exclusive of `end`, adding `+ 1` makes
  > the returned slice length `page_size + 1` instead of `page_size`. E.g.
  > `page(list(range(10)), 1, 3)` now returns `[0, 1, 2, 3]` (4 items)
  > instead of `[0, 1, 2]`. Every caller of `page()` receives one extra,
  > duplicated-across-pages item per page — consumers relying on a fixed
  > page size ... will show/return incorrect data, and adjacent pages will
  > overlap by one element.
- Expected claim: *"the page end index adds one to offset + page_size, so
  each page returns one extra item that also appears as the first item of
  the next page."*
- Manual judgment: **`SEMANTICALLY_EQUIVALENT`** — same root cause (`+ 1` on
  the slice end computed from `offset + page_size`), same consequence
  (one extra item per page, adjacent-page overlap), understandable without
  the fixture, no missing causal detail; if anything more precise than the
  fixture's own claim (it derives the exact resulting count and cites
  Python slice-exclusivity as the mechanism).
- Normalized content-token overlap (`match-criteria.md` §4.2 procedure,
  applied by hand): expected token set ≈ 15 unique tokens
  (`page, end, index, adds, one, offset, page_size, each, returns, extra,
  item, also, appears, first, next`); produced token set ≈ 65+ unique
  tokens (rich prose, code identifiers, a worked numeric example).
  Intersection ≈ `{page, end, offset, page_size, returns, extra, item,
  one}` — 8 tokens. Neither set is a subset of the other. Jaccard ≈
  `8 / (15 + 65 − 8) ≈ 0.11` — below the 0.25 `RELATED` floor →
  **`UNRELATED`**, confirmed by the actual `NO_MATCH` result.
- **This is a lexical matcher false negative**: both sides are
  substantively, verifiably correct about the same defect; the matcher's
  token-overlap mechanics are the gap. The richer and more precise the
  reviewer's real prose gets (numeric worked example, mechanism
  explanation, consequence framing), the *more* dilutive tokens it adds
  relative to the fixture's terse claim, which *lowers* Jaccard — richness
  is actively penalized by this design.

### Run C — lexical matcher false negative

- Produced claim (title + `Evidence`): command-injection root cause
  (`name` interpolated into an `f"..."` shell string, passed to
  `subprocess.run(cmd, shell=True, check=True)`), a worked exploit example,
  and impact (arbitrary command execution / host compromise / data
  exfiltration).
- Expected claim: *"name is interpolated into a shell command string that
  runs with shell=True, so a crafted name executes arbitrary commands
  (command injection)."*
- Manual judgment: **`SEMANTICALLY_EQUIVALENT`** — identical defect
  (untrusted `name` interpolated into a `shell=True` command string),
  identical consequence (arbitrary command execution), correctly located.
- Token overlap: expected set ≈ 13 unique tokens; produced set ≈ 70+ unique
  tokens (CVE-style exploit walkthrough, mitigation contrast against the
  prior safe implementation). Intersection ≈ `{name, shell, command,
  string, arbitrary, injection}` — 6 tokens. Jaccard ≈
  `6 / (13 + 70 − 6) ≈ 0.08` → **`UNRELATED`**, confirmed by the actual
  `NO_MATCH` result. Notably the expected claim's verb "interpolated" and
  the produced claim's near-synonyms ("unsanitized ... in shell string",
  "interpreted ... rather than treated as a literal filename") never
  share a token — the same mechanism described in different words is
  exactly what plain token overlap cannot bridge.

### Run D — lexical matcher false negative

- Produced claim (title + `Evidence`): duplicated `format_message(user)`
  call across the `email`/`sms` branches, framed as a maintainability
  concern with a concrete future-cost consequence.
- Expected claim: *"the sms branch repeats msg = format_message(user)
  verbatim from the email branch instead of computing msg once before the
  dispatch."*
- Manual judgment: **`SEMANTICALLY_EQUIVALENT`** — same defect (duplicated
  `format_message(user)` call between the two branches), same consequence
  class (maintainability / future-edit risk).
- Token overlap: expected set ≈ 13 unique tokens; produced set ≈ 50+ unique
  tokens. Intersection ≈ `{branch, email, sms, msg, format_message, user,
  instead}` — 7 tokens. Jaccard ≈ `7 / (13 + 50 − 7) ≈ 0.13` →
  **`UNRELATED`**, confirmed by the actual `NO_MATCH` result.

## 4. False-negative rate and pattern

Of the four executed runs, **all four** were manually judged
`SEMANTICALLY_EQUIVALENT` to their expected finding (Run A minimally so, on
a thin reviewer output that particular invocation), and **zero** achieved
`MATCH` or even `NEAR_MISS` under the current lexical matcher. Restricting to
the three runs with full, richly-evidenced claims (B, C, D — the cases this
study can attribute cleanly to the matcher rather than to reviewer
verbosity), the **lexical claim-correspondence false-negative rate is 3/3
(100%)** on this sample, with Jaccard scores of 0.08–0.13 in every case —
well under half the 0.25 `RELATED` floor, not a borderline miss.

Distinguishing the three failure categories #343 asks for:

- **Genuinely under-specified reviewer finding**: 1 of 4 (Run A) — a
  distinct, real phenomenon (reviewer output verbosity varies run to run,
  and `_build_claim` only appends `Evidence`/`Impact`/`Details` when the CLI
  actually rendered them), but not itself a matcher-design defect.
- **Fixture expectation problem**: 0 of 4 — every fixture claim in this
  sample is a plain, unremarkable restatement of the defect; nothing
  suggests unnaturally idiosyncratic wording no correct reviewer would
  reproduce.
- **Lexical matcher false negative**: 3 of 4 (Runs B, C, D) — the dominant,
  reproducible pattern. In every case the produced claim is longer, more
  detailed, and *more* precise than the fixture's own claim, and that
  extra correct detail is exactly what drives the Jaccard score down.

## 5. Root cause: `defect_kind` is designed for this, and never reaches production

`match-criteria.md` §4.1 already specifies a decisive, non-lexical first
check: *"`defect_kind` decides when both sides have one. Equal slugs →
`CORRESPONDS`."* All three corpus cases in this sample carry a fixture-side
`defect_kind` (`off-by-one`, `command-injection`, `duplicated-logic`). But
`runtime_platform/benchmark/scripts/benchmark_review_adapter.py::parse_review_output` has no
regex or field for a produced `defect_kind` — because the packaged
`local-code-review` finding rendering
([`../../shared/templates/finding-rendering.md`](../../shared/templates/finding-rendering.md))
has no field for one at all. Every produced finding in this study, and by
construction every produced finding the production adapter has ever parsed,
carries `defect_kind: None`. Per §4.1's own text, *"a missing `defect_kind`
on either side is not a wildcard; fall through to the claim comparison"* —
so **the free-text Jaccard/subset path is not one option among several in
production; it is the only path that has ever actually run**, despite
`match-criteria.md` ranking it last by design.

This reframes the finding: the lexical design is not necessarily inadequate
*in isolation* — it has never been tested *as the fallback it was designed
to be*, because the primary, more precise signal it was meant to back up has
never been wired up end to end.

## 6. Recommendation

Per #343's guardrail (exhaust deterministic structured-correspondence
options before a non-deterministic judge, in the stated preference order),
the first and cheapest lever is **1. stable defect identity / `defect_kind`
as the primary correspondence signal** — not because the other three are
ruled out, but because it is the only one of the four that is already fully
specified end to end in `match-criteria.md` and simply unpopulated on one
side.

**Recommended follow-up issue scope** (not implemented here, per #343
non-goals):

- Add a `defect_kind`-equivalent, machine-readable defect-class slug to the
  canonical full finding rendering
  ([`../../shared/templates/finding-rendering.md`](../../shared/templates/finding-rendering.md))
  that `local-code-review` (and, for parity, `github-pr-review`) actually
  emits per finding.
- Extend `benchmark_review_adapter.py::parse_review_output` to capture it
  into `ProducedFinding.defect_kind`, mirroring the existing `Evidence`/
  `Impact`/`Details` extraction pattern (#342).
- Re-run this same representative sample once that lands, and check whether
  `defect_kind` equality alone now resolves Runs B–D to `MATCH` without
  touching the lexical claim path at all.
- Only if that trial still leaves a material false-negative rate, proceed to
  option 2 (structured mechanism/evidence attributes) per the guardrail's
  stated order — do not skip ahead to option 2, 3, or 4 without that trial,
  and do not introduce an LLM/semantic judge unless options 1–3 are shown
  concretely insufficient.

### Open question: slug vocabulary stability

`defect_kind` slugs today are freeform, chosen independently by each
fixture's author (`off-by-one`, `command-injection`, `duplicated-logic`,
`missing-test`) with no enumerated, shared vocabulary between fixture
authoring and reviewer output. Equal-slug comparison (§4.1) only helps if
the reviewer, prompted independently, tends to converge on the *same* or a
mappable slug — untested by this study, since no produced finding here
carries one. A follow-up implementation issue must establish this before
treating option 1 as sufficient: either a closed, documented defect-kind
taxonomy the reviewer is instructed to draw from, or a normalization/mapping
step between independently-chosen slugs. This is exactly the kind of design
question #343 says a follow-up issue owns, not this research record.

### Explicit non-recommendations

- **Do not** conclude the current matcher is adequate — 3/3 well-evidenced,
  manually-verified-correct findings in this sample scored `NO_MATCH`, at
  Jaccard scores under half the `RELATED` floor.
- **Do not** conclude the fixtures need correction — no evidence of
  idiosyncratic fixture wording was found in this sample.
- **Do not** jump to an LLM/semantic judge — the guardrail's option 1 is
  untested in production (§5) and is the cheaper, fully-deterministic lever
  to try first.
- **Do not** change the 0.5/0.25 thresholds — per #343 non-goals, and
  because the observed scores (0.08–0.13) are not borderline; the finding is
  that the fallback path is systematically the wrong tool for verbose,
  correct reviewer prose, not that its knobs are mistuned.

## 7. Scope note: reviewer-verbosity variance (Run A)

Independent of matcher adequacy, Run A vs. Run B on the *identical* case and
input show the real CLI renders `Evidence` inconsistently across
invocations — one run produced a title-only finding, the next a fully
evidenced one. This affects both the false-negative analysis here (a thin
claim is harder to judge `SEMANTICALLY_EQUIVALENT` with confidence, though
Run A still was) and any future `defect_kind` rendering (an inconsistently
rendered field would reproduce the same gap in a new field). It is flagged
here as a fact this study observed, not adjudicated further — it is not
`match-criteria.md`'s concern (a #56/reviewer-output-quality question, and
per #343 non-goals, "fixing reviewer wording to mimic fixture phrasing" is
explicitly out of scope) and is not folded into the recommendation above.

## 8. Reproduction

```bash
python3 runtime_platform/benchmark/scripts/run_benchmark.py --case-id correctness-off-by-one-pagination --cli claude
python3 runtime_platform/benchmark/scripts/run_benchmark.py --case-id security-command-injection --cli claude
python3 runtime_platform/benchmark/scripts/run_benchmark.py --case-id quality-duplicated-branch-logic --cli claude
```

Each prints the run's `produced_findings` and the `metrics` block used in
§2–§4 above. Runs are not deterministic (real CLI reviewer output varies —
§7); re-running may reproduce different exact wording but, per this study,
is expected to reproduce the same `NO_MATCH` outcome under the current
matcher until `defect_kind` is populated on the produced side.

## 9. Follow-up: `defect_kind` wired to production (issue #355)

Issue #355 implemented this record's §6 recommendation and closed the §6
"Open question: slug vocabulary stability":

- `shared/templates/finding.md` ("Defect classification") and
  `shared/templates/finding-rendering.md` add an optional `defect_kind`
  finding field — a short, machine-readable, kebab-case defect-class slug
  — to the canonical finding contract both Skills render, following the
  same optional-provenance-field pattern as `confidence` (#178),
  `runtime validation` (#128), and `capability` (#83).
- `runtime_platform/benchmark/scripts/benchmark_review_adapter.py::parse_review_output`
  captures a rendered `Defect kind:` line into
  `ProducedFinding.extra["defect_kind"]`, mirroring the existing
  `Evidence`/`Impact`/`Details` extraction (#342).
- **Slug vocabulary stability** is resolved as a documented *naming
  convention*, not an enumerated closed taxonomy: `finding.md`, "Defect
  classification" instructs the reviewer to prefer the most specific
  well-established term for a familiar defect class (`race-condition`,
  not `bad-concurrency-handling`) rather than inventing a novel phrase,
  so independently authored slugs for the same defect class tend to
  converge. This matches how the existing fixture corpus's own
  `defect_kind` vocabulary was already organically freeform (dozens of
  distinct slugs across `docs/benchmark/corpus/`, no enumerated set) —
  an enforced closed enum would have required rewriting fixtures, which
  is out of scope (#355 non-goals).
- A real, non-hand-replayed rerun of this record's three reproduction
  cases (§8), against the issue #355 implementation, resolves all three
  to a clean `MATCH` (0 false negatives, 0 false positives each) via
  `defect_kind`-equality — not the lexical fallback:

  | Case | Produced `defect_kind` | Expected `defect_kind` | Result |
  |---|---|---|---|
  | `security-command-injection` | `command-injection` | `command-injection` | `MATCH` (was `NO_MATCH`) |
  | `correctness-off-by-one-pagination` | `off-by-one` | `off-by-one` | `MATCH` (was `NO_MATCH`) |
  | `quality-duplicated-branch-logic` | `duplicated-logic` | `duplicated-logic` | `MATCH` (was `NO_MATCH`) |

  The first attempt at each rerun, before the adapter's review prompt
  (`runtime_platform/benchmark/scripts/benchmark_review_adapter.py::_REVIEW_PROMPT`)
  explicitly named the `Defect kind` line, reproduced §7's
  reviewer-verbosity variance in a new form: `finding.md` defines the
  field, but the CLI did not reliably render it on an unprompted first
  try (0/3 runs rendered it). The prompt was strengthened to explicitly
  request `Defect kind` per `finding.md`'s "Defect classification",
  still populated at authoring time by the reviewer itself, not a
  post-hoc classifier — after which all three reruns rendered it and
  resolved to `MATCH` (3/3). This is a benchmark-harness-level prompt
  detail, not a packaged-Skill change: the field stays optional in
  `finding.md` for real (non-benchmark) usage.
