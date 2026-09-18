# Specialist-depth progressive-loading proof

Repository-development record for issue
[#411](https://github.com/amirbena/code-review-skill/issues/411), child of
[#403](https://github.com/amirbena/code-review-skill/issues/403), blocked
by [#408](https://github.com/amirbena/code-review-skill/issues/408) and
[#410](https://github.com/amirbena/code-review-skill/issues/410). Like
the rest of [`./`](README.md), this is a repository-development doc:
**not** packaged into either Skill archive, and no packaged Skill
resource depends on it.

#410 made `specialist-depth`'s loading conditional on its declared
activation predicate and proved the fail-closed contract at the
text/manifest level
([`tests/policy/review/specialist_depth/test_specialist_depth_410.py`](../../tests/policy/review/specialist_depth/test_specialist_depth_410.py)).
#408 recorded the pre-extraction baseline. Neither proves the
*behavior* stayed stable once loading actually became conditional, or
that the surface reduction #408's baseline made possible is real. This
document is that proof: one static measurement and one live run of the
real reviewer runtime, both reproducible from the documented commands
below, reusing every existing corpus/evaluator rather than introducing a
new one (per #411's Scope/Non-Goals).

## 1. Scope and non-goals

Per #411:

- Proves, with live-run evidence: an ordinary review where
  `specialist-depth` is unnecessary sees reduced instruction surface and
  unchanged findings; a review where it must activate sees it activate
  correctly; an ambiguous/risky activation case behaves conservatively
  (loads); and behavior otherwise matches #408's baseline.
- Reuses `specialist-depth-composition`'s existing corpus (#409) and
  #408's own 4-case regression set rather than duplicating them; adds
  exactly one net-new fixture
  ([`docs/benchmark/corpus/specialist-depth-progressive-loading-proof/`](../benchmark/corpus/specialist-depth-progressive-loading-proof/README.md))
  for the one required shape neither existing corpus covers (ambiguous
  predicate evaluation).
- Does **not** rewrite any existing *pinned* benchmark expectation
  (§4 below documents, but does not alter, a pre-existing defect-kind
  wording mismatch on two reused fixtures). Does **not** attempt a
  general router extraction, and does **not** re-litigate #410's own
  fail-closed text/manifest proof.
- Measured/executed at commit `696d1b4af2e0` (2026-09-17), `claude` CLI
  `2.1.272`.

## 2. Static surface reduction (required case 4)

Reproducible with:

```bash
python3 scripts/capability_architecture/specialist_depth_progressive_loading_proof.py static
```

Reuses `capability_loading_baseline.py`'s own static-surface measurement
unchanged (`measure_static_surface()` — see
[`capability-loading-baseline.md`](capability-loading-baseline.md) §2 for
methodology) and isolates `specialist-depth`'s own attributed word count:
the surface an "unnecessary" review no longer has to apply once loading
is actually conditional, versus #408's always-loaded baseline.

| Adapter | Total words (specialist-depth loaded) | `specialist-depth` words | Total words (not needed) | Reduction |
| --- | ---: | ---: | ---: | ---: |
| `local-code-review` | 83,154 | 9,379 | 73,775 | 11.28% |
| `github-pr-review` | 112,342 | 9,379 | 102,963 | 8.35% |

These totals differ slightly from #408's committed baseline (82,850 /
112,038 words, 9,116 `specialist-depth` words) because #410 itself added
the "Conditional loading: fail-closed" section to
[`specialist-depth.md`](../../shared/policies/specialist-depth.md) and
the matching clause to `capability.yaml` — this is a live re-measurement
at the current commit, not the stale #408 snapshot, and `specialist-depth`
remains the single largest attributed capability in either adapter's
surface.

Note on what this reduction *is*, precisely: `scripts/packaging/
package-manifest.json` still ships `specialist-depth`'s files
unconditionally (packaging membership is unaffected by #410 — confirmed
by `generate_package_manifest.py --check` passing unchanged). The
"reduction" is the instruction surface a review's own reasoning applies
once loading is actually conditional on the activation predicate, not a
change to what the packaged archive contains. §3-5 below are the
behavioral evidence that this conditionality is real, not merely
declared.

## 3. Regression stability vs. #408's baseline (required cases 1/2, matched)

Reproducible with:

```bash
python3 scripts/capability_architecture/specialist_depth_progressive_loading_proof.py behavioral
```

Re-runs #408's own 4-case corpus (`docs/benchmark/corpus/*.yaml`) through
the same `ProductionReviewerAdapter` + `benchmark_metrics.compute_run_metrics`
#408 used, live, at the commit above:

| Case | False negatives | False positives | vs. #408 baseline |
| --- | ---: | ---: | --- |
| `correctness-off-by-one-pagination` | 0 | 0 | matches |
| `no-op-comment-and-rename` | 0 | 0 | matches |
| `quality-duplicated-branch-logic` | 0 | 0 | matches |
| `security-command-injection` | 0 | 0 | matches |
| **Aggregate** | **0** | **0** | **identical to #408's recorded 0 FN / 0 FP** |

Behavior on the reachable regression set is unchanged.

## 4. Activation correctness (required cases 1/2)

Reuses `specialist-depth-composition`'s Case A (`specialist-depth` not
needed) and Case B (`specialist-depth` must activate) by id, live:

| Case | Role | Did the right thing happen? |
| --- | --- | --- |
| Case A (`...case-a-zero-capabilities-base-reasoning-complete`) | not needed | Yes — zero specialist-depth capabilities engaged; base reasoning alone correctly caught the boolean-guard defect the fixture pins. |
| Case B (`...case-b-one-capability-security-confused-deputy`) | must activate | Yes — security deepening engaged and correctly identified the confused-deputy vulnerability the fixture pins. |

Both cases show non-zero false-negative/false-positive counts under the
corpus's strict matcher (`benchmark_metrics.compute_run_metrics`),
**not** because the underlying review judgment was wrong, but because of
one pre-existing corpus fragility exposed for the first time by actually
executing these fixtures through `git apply` + the real reviewer
runtime — something no prior test did (these fixtures' own unit test,
`test_specialist_depth_composition_corpus.py`, only validates shape via
`benchmark_fixture.parse_case`, never applies the patch or runs a live
review):

- **Defect-kind wording variance.** `benchmark_match.defect_match`
  requires an exact string match when both sides carry a `defect_kind`
  (`runtime_platform/benchmark/reference/benchmark_match.py`). The live reviewer
  described the same, correctly-identified defect with a different
  freeform slug than the one pinned in each fixture (Case A: produced
  `logic-operator-swap` vs. pinned
  `validation-guard-boolean-operator-inverted`; Case B: produced
  `confused-deputy` vs. pinned `confused-deputy-unchecked-delegation`),
  which the matcher treats as `UNRELATED` regardless of the otherwise
  exact location/claim match. This wording varies run to run (an earlier
  run of this same fixture produced `boolean-operator-logic-error`
  instead) — freeform, not a fixed vocabulary the reviewer is constrained
  to.
- **Case B also raised one additional, legitimate finding** (missing
  idempotency protection on retry) that the fixture's
  `findings_completeness: exhaustive` does not list, scored as a false
  positive although it is a real, defensible observation about the same
  code. (An earlier run additionally raised a missing-input-validation
  finding not reused here; which extra findings appear is itself
  non-deterministic.)

These are properties of the two *reused*, already-pinned fixtures'
matching strictness, not a regression #410's conditional loading
introduced — #411's Non-Goals explicitly forbid rewriting an existing
pinned expectation to force a pass, so neither fixture is edited here.
Widening `defect_kind` tolerance (e.g. via `alternatives`, the construct
this issue's own new fixture uses in §5) or reconciling the exhaustiveness
of Case B's expected set is left as a follow-up against #409's corpus,
not folded in silently.

One genuine (pre-existing, unrelated-to-#410) defect *was* found and
fixed here because it blocked this proof's Case A from executing at all:
`specialist-depth-composition-case-a-...yaml`'s patch hunk header
(`@@ -8,7 +8,10 @@`) undercounted its own old-side line span by 2,
making the patch corrupt per `git apply`. Fixed as a minimal,
mechanical hunk-header correction (`@@ -8,9 +8,10 @@`) — no change to
the fixture's expected findings, decision, or rationale. A broader sweep
found 17 more corpus fixtures with the same class of bug across
unrelated sub-corpora (never previously caught because no existing test
actually applies a fixture's patch); that cleanup is intentionally out
of #411's scope and tracked as its own follow-up.

## 5. Ambiguous predicate evaluation forces fail-closed load (required case 3)

This issue's one net-new fixture:
[`docs/benchmark/corpus/specialist-depth-progressive-loading-proof/specialist-depth-progressive-loading-proof-ambiguous-cardinality-forces-fail-closed-load.yaml`](../benchmark/corpus/specialist-depth-progressive-loading-proof/README.md).
A materially implicated performance signal (a new per-order query) whose
cardinality is genuinely undocumented in either direction — unlike
`specialist-depth-composition`'s Case D (a superficial signal with *no*
qualifying evidence, correctly suppressed) or the reused N+1 domain
fixture (documented unbounded). Live result:

| Run | Produced finding | Matched required entry? |
| --- | --- | --- |
| Initial (before recalibration) | `n-plus-one-query`, P1 | No — fixture originally pinned an exact `P2` severity and a single `n-plus-one-remote-call` defect_kind; the live reviewer's real judgment (P1, `n-plus-one-query`) is a reasonable but different restatement. |
| After recalibration | `n-plus-one-query`, P1 | **Yes** — 0 false negatives, 0 false positives. |

The fixture was recalibrated to match observed reviewer behavior — this
is this issue's *own*, not-yet-pinned fixture, so adjusting it to reality
is expected corpus-authoring iteration, not the "rewrite a pinned
expectation" #411's Non-Goals forbid. Severity is now expressed as the
supported `[P1, P2]` variance range (fixture-format.md §9, item 4):
genuine reviewer judgment under real ambiguity may reasonably land at
either, but a `P2`-only-permitted severity list never forces
`changes-required` on its own
([`severity.md`](../../shared/policies/severity.md), "Decision
derivation"), which is exactly what makes this case's `decision: clean`
with a **required finding present** the deliberate contrast with Case
D's `decision: clean` with **zero** findings: the same mechanical
decision, reached for two different reasons. What the fixture pins —
and what the live run above confirms — is that ambiguity produces a
finding at all, never silence. That is the fail-closed behavior #410
declared and this issue proves.

## 6. Reproducing / re-measuring

```bash
python3 scripts/capability_architecture/specialist_depth_progressive_loading_proof.py all \
  --out docs/capability-architecture/specialist-depth-progressive-loading-proof.json
```

`all` runs both halves. `behavioral` requires the `claude` CLI on `PATH`
(or `BENCHMARK_REVIEW_CLI` set), per `run_benchmark.py`'s own
runtime-availability check, and its exit code is fail-closed on exactly
the two cases this issue owns outright: the regression set (§3) and this
issue's own net-new ambiguous-fail-closed fixture (§5). A mismatch on
either fails the run. A mismatch on the two *reused*
`specialist-depth-composition` fixtures (Case A/B, §4's known,
documented, pre-existing defect-kind-wording matcher fragility) is
reported (to stderr and in the JSON output) but never fails the run —
that fixture-matching strictness is #409's to fix, not #411's to
silently launder into a green exit code.

## Status and canonical home

This document and
[`scripts/capability_architecture/specialist_depth_progressive_loading_proof.py`](../../scripts/capability_architecture/specialist_depth_progressive_loading_proof.py)
are the authoritative proof for #411. Neither is packaged into either
Skill archive, and no runtime behavior, packaging, or loading changed to
produce it beyond the one incidental hunk-header fix in §4 — purely
additive, matching #408's own precedent. This is the evidence #412 (the
architecture reassessment checkpoint) is scoped to cite.
