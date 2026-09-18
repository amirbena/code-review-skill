# Specialist-Depth Progressive-Loading Proof Corpus

Repository-development artifact for GitHub Issue
[#411](https://github.com/amirbena/code-review-skill/issues/411), child of
epic [#403](https://github.com/amirbena/code-review-skill/issues/403).
Issue [#410](https://github.com/amirbena/code-review-skill/issues/410)
made `specialist-depth`'s loading conditional on its declared activation
predicate and proved the fail-closed contract at the **text/manifest**
level ([`test_specialist_depth_410.py`](../../../../tests/policy/review/specialist_depth/test_specialist_depth_410.py)).
This corpus supplies the one thing that proof does not: a
**behavioral** fixture pinning what a correct review must actually
*produce* when predicate evaluation is genuinely ambiguous — the shape
[`specialist-depth-composition/`](../specialist-depth-composition/README.md)
does not cover.

Every case conforms to [`../../fixture-format.md`](../../../../runtime_platform/benchmark/fixture-format.md)
and is a self-contained inline `patch` plus its `base` pre-image, so the
corpus runs without network access. Like the rest of [`../`](../README.md)
and [`../../`](../../../../runtime_platform/benchmark/README.md) this is **not** packaged into either Skill
archive and no packaged Skill resource depends on it — it is consumed
only by this repository's own test suite, through the single reference
validator
[`../../../../runtime_platform/benchmark/reference/benchmark_fixture.py`](../../../../runtime_platform/benchmark/reference/benchmark_fixture.py)
(never a second one).

## Selection principle: one net-new case, everything else reused

Issue #411's Scope requires reusing the existing `specialist-depth`
corpora and the routing-decision corpus from
[#409](https://github.com/amirbena/code-review-skill/issues/409) rather
than duplicating them, and forbids rewriting any existing pinned benchmark
expectation. Concretely, of #411's four required cases:

1. **Ordinary review, `specialist-depth` not needed** — reused from
   [`specialist-depth-composition/`](../specialist-depth-composition/README.md)'s
   Case A (zero capabilities engage; base reasoning stays complete).
2. **A review where it must activate** — reused from that same corpus's
   Case B (exactly one capability engages: the confused-deputy fixture).
3. **An ambiguous/risky activation case, shown to load conservatively** —
   this directory's **one** new fixture,
   [`specialist-depth-progressive-loading-proof-ambiguous-cardinality-forces-fail-closed-load.yaml`](specialist-depth-progressive-loading-proof-ambiguous-cardinality-forces-fail-closed-load.yaml).
4. **A direct before/after surface-reduction comparison against #408's
   baseline** — the static word-count comparison recorded in
   [`../../../capability-architecture/specialist-depth-progressive-loading-proof.md`](../../../capability-architecture/specialist-depth-progressive-loading-proof.md),
   reusing
   [`capability_loading_baseline.py`](../../../../scripts/capability_architecture/capability_loading_baseline.py)'s
   existing static-surface measurement rather than a new evaluator; no
   fixture of its own.

Cases 1 and 2 are exercised here only by reference (this directory does
not re-declare them); the proof script
([`specialist_depth_progressive_loading_proof.py`](../../../../scripts/capability_architecture/specialist_depth_progressive_loading_proof.py))
loads them directly from `specialist-depth-composition/` by id.

### Why the ambiguous case needs its own fixture

`specialist-depth-composition/`'s own Case D already pins confident
**non**-activation (a superficial path/file-type signal alone, with zero
qualifying semantic evidence) and Cases B/C/E/F/G pin confident
activation (unambiguous domain evidence). Neither shape exercises what
#410's fail-closed clause actually governs: predicate evaluation that
cannot be confidently resolved either way from the evidence present. This
corpus's one case is deliberately in that gap — a materially implicated
performance signal (a newly added per-order query, semantic evidence, not
a path/file-type match) whose cardinality is genuinely undocumented in
either direction, unlike the reused N+1 fixture (documented unbounded)
or the domain corpus's constant-size-loop fixture (documented small and
fixed). The expected outcome pins that ambiguity must still load
performance deepening — a required finding is produced — while its
permitted severity range (`P1` or `P2`, never the reused fixture's
confident `P0`) lets genuine reviewer judgment under real ambiguity vary:
specialist-depth's own "never" list forbids manufacturing confidence the
evidence does not support, but it does not dictate exactly how
conservatively that ambiguity is scored. Because not every value in a
`P1`/`P2` severity range is blocking, this required finding never forces
`changes-required` on its own
([`severity.md`](../../../../shared/policies/severity.md), "Decision
derivation"), which is what makes this case's `decision: clean` +
non-empty `findings` combination the deliberate contrast with Case D's
`decision: clean` + **empty** `findings`: the same mechanical decision,
reached for two different reasons — one is silence because nothing is
implicated, the other is a finding because loading happened, whatever its
exact severity turns out to be.

## Cases

| File | Shape | A correct review must… | Decision |
|---|---|---|---|
| [`specialist-depth-progressive-loading-proof-ambiguous-cardinality-forces-fail-closed-load.yaml`](specialist-depth-progressive-loading-proof-ambiguous-cardinality-forces-fail-closed-load.yaml) | ambiguous predicate evaluation (ambiguous evidence, ≠ Case D's absent evidence) | report one **P1-or-P2** per-order-query finding rather than staying silent | `clean` |

## Validation

[`../../../../tests/unit/benchmark/test_specialist_depth_progressive_loading_proof_corpus.py`](../../../../tests/unit/benchmark/test_specialist_depth_progressive_loading_proof_corpus.py)
loads this directory's fixture through the same single reference
validator used everywhere else in this corpus tree (it never defines a
second one), and asserts: the directory holds exactly the one case; it
carries a required finding permitting only `P1`/`P2` (never `P0`, which
would collapse the "ambiguity, not confident escalation" distinction this
case exists to pin) that does not by itself force `changes-required`; its
mechanically derived decision is `clean`; and it
is distinct from `specialist-depth-composition`'s Case D by actually
carrying a finding. Live execution proof — running this fixture plus the
reused Case A/B and the #408 regression set through
`ProductionReviewerAdapter` and recording the result — is
[`specialist-depth-progressive-loading-proof.md`](../../../capability-architecture/specialist-depth-progressive-loading-proof.md),
not this test file; matching a reviewer's output to this fixture's
expectations and scoring it are out of scope here (Issues #41/#52/#54),
same as every other corpus in this tree.
