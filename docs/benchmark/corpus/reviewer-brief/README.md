# Reviewer Brief Benchmark Corpus

Repository-development artifact for GitHub Issue
[#309](https://github.com/amirbena/code-review-skill/issues/309), which
depends on [#304](https://github.com/amirbena/code-review-skill/issues/304)
(`skills/github-pr-review/policies/reviewer-brief.md` and
`skills/github-pr-review/templates/reviewer-brief.md`): a benchmark/
workbench fixture set pinning the **semantic quality** and **publication
isolation** of the private, caller-facing `Reviewer Brief` every
`github-pr-review` result includes.

## Why this corpus is not `benchmark-case/v1` fixtures

Unlike every sibling directory here (`security-deepening/`,
`api-compatibility/`, `specialist-depth-composition/`, …), this corpus
does **not** ship `benchmark-case/v1` YAML fixtures. That format
([`../../fixture-format.md`](../../fixture-format.md)) is closed and
findings/decision-shaped: `expected.findings` and `expected.decision` are
the only outcome it can pin. The Reviewer Brief is a different kind of
artifact entirely — private prose, synthesized *after* findings/decision
are already finalized, and required to be **absent** from the GitHub-bound
review body/inline comments those same findings populate. Neither "the
brief's content" nor "which of two output surfaces a string appears in"
has a field in that schema, for the same reason
[`../specialist-depth-composition/README.md`](../specialist-depth-composition/README.md)
and [`../risk-depth/README.md`](../risk-depth/README.md) already document
for their own mechanisms: extending the schema for one artifact would
either weaken its closedness for every other corpus or fork a second,
parallel one — both of which Issue #309 explicitly asks this work to
avoid ("Reuse the repository's existing benchmark architecture rather
than creating a parallel fixture framework").

Instead, this corpus follows the same **test-only reference model**
pattern the rest of `docs/benchmark/` already uses for machinery that has
no packaged production twin (`tests/reference/benchmark/benchmark_fixture.py`,
`benchmark_match.py`, `benchmark_runner.py`, …):
[`../../../../tests/reference/benchmark/reviewer_brief_fixtures.py`](../../../../tests/reference/benchmark/reviewer_brief_fixtures.py)
defines one `ReviewerBriefCase` per required scenario, carrying **both**
the private brief's field values **and** the GitHub-bound review
body/inline comments the same invocation would publish, so isolation is
checked between two concrete artifacts, never inferred from one.

## Two-layer evaluation model

Per Issue #309's "Evaluation model", kept deliberately separate from
ordinary finding precision/recall (`match-criteria.md`,
`missed-and-incorrect-findings.md`, `severity-accuracy.md`,
`duplicate-noise.md` above this corpus in the tree):

1. **Deterministic structural layer** — properties with one correct
   shape: required fields present, `User-provided focus` faithfully
   verbatim-or-`none provided`, 2-4 `Manual review focus` bullets, no
   `P0`/`P1`/`P2` label without a finalized-finding reference, no
   `Evidence:`/`Impact:`/`Fix:` duplication, delta/stacked/partition scope
   discipline, and zero publication leakage. Machine-checked in
   [`../../../../tests/unit/benchmark/test_reviewer_brief_structural.py`](../../../../tests/unit/benchmark/test_reviewer_brief_structural.py)
   and
   [`../../../../tests/unit/benchmark/test_reviewer_brief_publication_isolation.py`](../../../../tests/unit/benchmark/test_reviewer_brief_publication_isolation.py).
2. **Rubric/reference layer** — properties where wording is intentionally
   flexible and no single correct string exists: whether the independently
   derived focus item is genuinely *useful* to a human reviewer, whether
   the senior-voice rendering reads as well as the structured one. Exactly
   like [`../../senior-voice-examples.md`](../../senior-voice-examples.md),
   this is a **documented reference set, not a CI gate**:
   [`../../reviewer-brief-examples.md`](../../reviewer-brief-examples.md).

Golden-string tests are deliberately avoided anywhere semantic
equivalence, not exact wording, is the actual contract (Issue #309,
"Do not introduce brittle golden-string tests…") — the structural layer
asserts field shape and keyword/marker presence-or-absence, never full
paragraph equality, and the `human_review_output` on/off pair is compared
by shared required keywords and field-set equality, not string equality.

## Required coverage

Every scenario Issue #309 requires is tagged in
`reviewer_brief_fixtures.py` (`REQUIRED_COVERAGE_TAGS`), and
`test_reviewer_brief_structural.py`'s `CoverageCompletenessTests` asserts
every tag is covered by at least one case — the "the fixture set covers
all cases above" acceptance criterion is machine-checked, not a manual
claim:

| Case | Required scenario(s) covered |
| --- | --- |
| `clean-pr-no-user-focus` | clean PR, no user focus: useful `What changed` + independently-derived manual focus; passive review returns the brief; clean review stays useful (not `REVIEW CLEAN`) |
| `trusted-focus-active-review` | trusted user focus represented + independent focus added beyond it; active review: brief available to caller, absent from GitHub; findings inform focus without duplicating Evidence/Impact/Fix |
| `misleading-user-focus` | misleading/irrelevant focus: brief stays grounded in the actual diff, invents no finding, still represents the caller's words faithfully |
| `conflicting-user-focus` | user focus conflicts with repository evidence: the actual change (a breaking removal) stays authoritative over the caller's contrary claim |
| `delta-re-review-scope` | delta re-review: summarizes the reviewed delta only, not the full historical PR |
| `stacked-pr-effective-layer` | stacked PR: summarizes the effective owned layer, not the whole stack |
| `large-pr-partitioned-aggregate` | large/partitioned PR: synthesizes the final aggregate target, no per-partition notes |
| `human-review-output-off` / `human-review-output-on` | `human_review_output` on/off: identical semantic fields and keywords, wording differs only |

## Adapter availability (Issue #309, "Validation")

Issue #309 asks to run the focused fixture set through the real reviewer
adapter "where available."
[`../../../../scripts/benchmark/benchmark_review_adapter.py`](../../../../scripts/benchmark/benchmark_review_adapter.py)
(`ProductionReviewerAdapter`, #250) only drives `local-code-review` — its
fixed CLI prompt invokes that Skill by name, and its output parser
recognizes only that Skill's single-surface Markdown finding format.
`local-code-review` has no Reviewer Brief (that is an explicit non-goal
of #304) and no dual-surface (GitHub-bound vs. private) output to
separate. Building a second adapter that drives `github-pr-review`
end-to-end against a real GitHub PR, with a new prompt and a new
dual-surface parser, is materially new adapter infrastructure, not a
reuse of the existing one — and is out of #309's narrow benchmark/
evaluation scope (it would also require live GitHub write access the
existing adapter's disposable-workspace design deliberately avoids). This
corpus therefore evaluates the reference model directly, exactly as the
existing rubric layer (`senior-voice-examples.md`) already does for
presentation-quality properties the current adapter/corpus stack cannot
score either. If a `github-pr-review`-targeting adapter is added later,
these fixtures are already shaped to drive it: each `ReviewerBriefCase`'s
`what_changed` / `user_provided_focus_field` / `manual_review_focus` /
`open_questions` fields are exactly `templates/reviewer-brief.md`'s
canonical shape, and `github_review_body` / `github_inline_comments`
mirror `templates/external-review-summary.md` / `templates/inline-finding.md`.

## Validation

```bash
python3 -m pytest tests/unit/benchmark/test_reviewer_brief_structural.py \
  tests/unit/benchmark/test_reviewer_brief_publication_isolation.py -v
```

Both modules load the single reference fixture module above (never a
second one) and are independent of the `benchmark-case/v1` runner/matcher/
metrics stack, which this corpus does not touch.
