# Null-Like Absence-Risk Benchmark Corpus

Repository-development artifact for GitHub Issue
[#121](https://github.com/amirbena/code-review-skill/issues/121), the
cross-language review requirement in
[`shared/policies/review-scope.md`](../../../../shared/policies/review-scope.md),
"Null-like absence-risk review." This is a **focused sub-corpus** of
[`benchmark-case/v1`](../../fixture-format.md) fixtures exercising that
section's vocabulary: the cross-language semantic rule (never a regex or
keyword match), the credible-absence-path patterns, the interoperability /
escape-hatch boundaries, and the suppression rule for guarded,
type-guaranteed, or upstream-validated values.

Every case conforms to [`../../fixture-format.md`](../../fixture-format.md)
and is a self-contained inline `patch` plus its `base` pre-image, so the
corpus runs without network access. Like the rest of
[`../`](../README.md) and [`../../`](../../README.md) this is **not**
packaged into either Skill archive and no packaged Skill resource depends
on it — it is consumed only by this repository's own test suite, through
the single reference validator
[`../../../../tests/reference/benchmark/benchmark_fixture.py`](../../../../tests/reference/benchmark/benchmark_fixture.py)
(never a second one).

## Selection principle

**One case per way the rule must behave**, per Issue #121's acceptance
criteria: a real null/undefined/nil dereference risk surfaced; its
directly guarded counterpart correctly *not* reported (the suppression
rule, not an unrelated scenario); an optional/lookup-result path with
unchecked absence surfaced; JavaScript/TypeScript `undefined`/`null`
property access covered; and a null-safe-language interoperability edge
case (a Kotlin platform type from Java interop) covered. Together the
cases span Java, Go, TypeScript, and Kotlin/Java interop — at least
Java/Kotlin, JavaScript/TypeScript, and one of C#/Python/Go, per the
Issue's validation requirement.

## Cases

| File | Pattern exercised | A correct review must… | Decision |
|---|---|---|---|
| [`null-absence-java-unguarded-dereference.yaml`](null-absence-java-unguarded-dereference.yaml) | real dereference risk | catch a documented-nullable repository result dereferenced with no null check | `changes-required` |
| [`null-absence-java-guarded-clean.yaml`](null-absence-java-guarded-clean.yaml) | suppression — guarded equivalent | recognize the identical nullable result is checked with an early return before its only use, and report nothing | `clean` |
| [`null-absence-go-unchecked-map-lookup.yaml`](null-absence-go-unchecked-map-lookup.yaml) | unchecked optional/lookup result | catch a Go map lookup's nil zero-value dereferenced without the two-value `ok` check | `changes-required` |
| [`null-absence-typescript-optional-property-access.yaml`](null-absence-typescript-optional-property-access.yaml) | JS/TS undefined property access | catch an explicitly optional (`address?: Address`) field's property accessed with no optional chaining or guard | `changes-required` |
| [`null-absence-kotlin-java-platform-type.yaml`](null-absence-kotlin-java-platform-type.yaml) | interoperability / escape hatch | catch a Kotlin call into a nullable-by-javadoc Java method (a platform type) used with no null check | `changes-required` |

The Java pair (`null-absence-java-unguarded-dereference.yaml` /
`null-absence-java-guarded-clean.yaml`) is a deliberately matched pair:
identical nullable source, identical call site, the only difference being
the presence of a guard — so a correct review's behavior is shown to turn
on reachability, not on the declared type alone.

Per-case provenance and a one- or two-sentence rationale also live in each
fixture's `metadata` block (`source`, `tags`, `rationale`) and in the
header comment.

## Validation

[`../../../../tests/unit/review/test_null_absence_corpus.py`](../../../../tests/unit/review/test_null_absence_corpus.py)
loads every `*.yaml` here through the same single reference validator
[`../../../../tests/reference/benchmark/benchmark_fixture.py`](../../../../tests/reference/benchmark/benchmark_fixture.py)
used for the worked example and every other corpus. It never defines a second
one, and asserts: the sub-corpus stays small and documented; every
required case is present; every case pins an explicit `decision`
consistent with its required findings; the guarded/unguarded pair produces
exactly one finding between them, on the unguarded case only; and every
finding's anchor resolves inside its own case's patch or base. Matching a
reviewer's output to these expectations and scoring it are out of scope
here (Issues #41 / #52 / #54). Peer review of the expected findings
themselves happens on the pull request.
