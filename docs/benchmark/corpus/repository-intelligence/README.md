# Repository-Intelligence Benchmark Corpus

Repository-development artifact for GitHub Issue
[#129](https://github.com/amirbena/code-review-skill/issues/129). This is a
**focused sub-corpus** of [`benchmark-case/v1`](../../fixture-format.md)
fixtures demonstrating the acceptance criterion "benchmark fixtures
demonstrate measurable gains over diff-only review without unacceptable
false-positive growth" for the
[repository-intelligence model](../../../repository-intelligence/repository-intelligence-model.md)
— the typed entity/relationship model, retrieval bounds, provenance,
snapshot identity/staleness, and relationship-influence attribution that
sits inside the ring
[`../../../../shared/policies/repository-expansion.md`](../../../../shared/policies/repository-expansion.md)
(#87) already authorizes.

Every case conforms to [`../../fixture-format.md`](../../fixture-format.md)
and is a self-contained inline `patch` plus its `base` pre-image, so the
corpus runs without network access. Like the rest of
[`../`](../README.md) and [`../../`](../../README.md) this is **not**
packaged into either Skill archive and no packaged Skill resource depends
on it — it is consumed only by this repository's own test suite, through
the single reference validator
[`../../../../tests/reference/benchmark_fixture.py`](../../../../tests/reference/benchmark_fixture.py)
(never a second one).

## Selection principle

- **One case per #87 trigger the model targets, across two language
  shapes.** Call-site (Python), interface/contract (TypeScript), and
  config-consumer (Python) each get a positive case where the defect is
  only visible by resolving the relationship, plus one safe-failure
  (ambiguity) case and one negative/control case where retrieval succeeds
  but changes nothing.
- **Each positive case isolates one trigger.** The diff, read alone,
  contains nothing that reads as wrong; the defect exists only in
  combination with an unchanged file the diff never touches, supplied via
  `input.base`.
- **The control case proves retrieval breadth alone is not a finding.** It
  resolves a relationship exactly like the positive cases — successfully,
  with provenance — but the relationship is compatible with the change, so
  the correct output is no finding and an empty
  `influential_relationships`.
- **The safe-failure case proves ambiguity is never invented away.** A
  trigger fires but the concrete relationship cannot be resolved
  statically; the correct output is an unresolved diagnostic, never a
  guessed relationship or a manufactured finding.
- **`exhaustive` completeness** on every case, so an unexpected finding —
  in either direction — is itself a corpus failure.
- **Intentionally small.** Illustrative, representative cases, not
  exhaustive coverage of every trigger/language combination.

## No statistical-significance claim

This is a small, hand-crafted, illustrative corpus. It demonstrates the
relationship-aware mechanism holding on representative cases; it is **not**
a measured hit-rate, precision/recall figure, or any other statistical
claim about review quality at scale. Turning matches and misses into
aggregate quality metrics is out of scope here — see
[`../../fixture-format.md`](../../fixture-format.md) §13 and
[#41](https://github.com/amirbena/code-review-skill/issues/41).

## Cases

| File | Trigger / language | A correct review must… | Decision |
|---|---|---|---|
| [`repo-intel-python-call-site-caller-null-deref.yaml`](repo-intel-python-call-site-caller-null-deref.yaml) | call-site, Python | resolve the untouched caller and report the caller-side null dereference the diff alone cannot show | `changes-required` |
| [`repo-intel-typescript-interface-contract-implementer-break.yaml`](repo-intel-typescript-interface-contract-implementer-break.yaml) | interface/contract, TypeScript | resolve the untouched sibling implementer and report it as inconsistent with the narrowed interface contract | `changes-required` |
| [`repo-intel-python-config-consumer-stale-import.yaml`](repo-intel-python-config-consumer-stale-import.yaml) | config-consumer, Python | resolve the untouched consumer file and report the stale import the renamed config key breaks | `changes-required` |
| [`repo-intel-python-dynamic-dispatch-safe-failure.yaml`](repo-intel-python-dynamic-dispatch-safe-failure.yaml) | call-site (ambiguous), Python | leave the string-keyed dynamic dispatch unresolved and report **nothing** — never invent which concrete subclass is affected | `clean` |
| [`repo-intel-python-control-compatible-caller-no-finding.yaml`](repo-intel-python-control-compatible-caller-no-finding.yaml) | call-site (control), Python | resolve the caller successfully, with provenance, and still report **nothing** because the relationship is compatible | `clean` |

Per-case provenance and a one- or two-sentence rationale also live in each
fixture's `metadata` block (`source`, `tags`, `rationale`) and in the
header comment.

## Relationship-influence attribution and staleness are reference-model concerns

`benchmark-case/v1` has no field for `influential_relationships` or a
snapshot-identity/staleness state — the format's schema is closed and this
corpus does not extend it (see
[`../../fixture-format.md`](../../fixture-format.md) §2, "an unknown key
anywhere is a rejection"). Those concerns are proven at the reference-model
level instead: each case above has a matching case in
[`../../../../tests/unit/test_repository_intelligence.py`](../../../../tests/unit/test_repository_intelligence.py)
that exercises
[`../../../../tests/reference/repository_intelligence.py`](../../../../tests/reference/repository_intelligence.py)
directly — constructing the same resolved relationship (or unresolved
candidate) the fixture's rationale describes, asserting its
`influential_relationships` membership, and asserting current/stale
snapshot handling. The corpus fixture pins the **expected finding
outcome**; the reference-model case pins the **relationship-level
mechanism** that outcome rests on. Language tagging (Python / TypeScript)
is likewise carried in each file's `id`, `title`, and this table, not in
`metadata.tags` (a closed vocabulary that does not include language
values).

## Validation

[`../../../../tests/unit/test_repository_intelligence_corpus.py`](../../../../tests/unit/test_repository_intelligence_corpus.py)
loads every `*.yaml` here through the same single reference validator
[`../../../../tests/reference/benchmark_fixture.py`](../../../../tests/reference/benchmark_fixture.py)
used for the worked example and the #51 corpus (it never defines a second
one), and asserts: the sub-corpus stays small; per positive fixture, the
relationship-dependent defect is absent from what a diff-only read of the
patch alone would show and present in the fixture's expected findings; the
control fixture's expected findings stay empty (no added finding, no false
positive); the safe-failure fixture's expected findings stay empty; and at
least two distinct language shapes are represented across the corpus.
Matching a reviewer's output to these expectations and scoring it are out
of scope here (Issues #41 / #52 / #54).
