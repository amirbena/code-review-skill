# Shared Policy — Null-Like Absence-Risk Review

Applies identically to `local-code-review` and `github-pr-review`. It owns
the cross-language null-like absence-risk pass: the credible-absence-path
patterns, the interoperability and escape-hatch boundaries that weaken a
language's normal null-safety guarantees, and the suppression rule that
keeps this a semantic, evidence-gated rule rather than a keyword or regex
match.

This is a sub-domain of [`review-scope.md`](review-scope.md), which owns
base review scope and routes here. It introduces no new finding category
or severity: a surfaced risk is classified per [`severity.md`](severity.md)
and evidenced per [`evidence.md`](evidence.md) exactly like any other
finding.

## Null-like absence-risk review

Inspect changed data-flow and control-flow for credible **null-like
absence** risk — null-pointer dereference, `undefined` / `null` property
or method access, `nil` dereference, `None` attribute/index access, an
unchecked optional-lookup result, or a nullable return value assumed
present — whenever the reviewed language admits that failure mode at all.
This is a **semantic rule keyed to the reviewed language's nullability
model, never a regex or keyword match**: it applies identically whether
the language is Java/Kotlin, JavaScript/TypeScript, C#, Python, Go, or any
other language with equivalent null/nil/undefined semantics, and it reads
what a value's absence would actually do at the point of use, not whether
a variable is named `value` or a method is named `get`. A credible risk is
raised only when the diff's own evidence supports it; purely theoretical
nullability — a value that could in principle be null somewhere in the
type system but is demonstrably safe at every reachable use the diff
introduces — is not reported. This section adds no new finding category:
a surfaced risk is classified under [`severity.md`](severity.md) and
evidenced per [`evidence.md`](evidence.md) exactly like any other finding,
and carries no dedicated severity merely because a nullable value is
present.

### Credible absence paths

Representative patterns — illustrative, not an exhaustive keyword list, and
not something to flag merely because the shape superficially appears:

- dereference, member/method access, invocation, indexing, or
  destructuring of a value before a null/undefined/nil/None check that the
  surrounding code elsewhere treats as necessary;
- an optional or lookup result (map/dictionary `get`, `find`, a query-one
  call, a configuration or environment lookup) used without handling the
  absent case;
- a nullable return value from a changed function assumed present by a
  caller, or a changed caller that drops a present absence-check on a
  callee's nullable return;
- JavaScript/TypeScript property or method access, indexing, or
  destructuring on a value that can be `null` or `undefined` at that point;
- a nullable collection element or map value used as though always
  present;
- a `nil` / `None` value passed into code that assumes a concrete,
  non-absent object.

### Interoperability and escape-hatch boundaries

Platform and language boundaries that weaken a language's normal
null-safety guarantees deserve the same scrutiny as ordinary flow, because
the type system can no longer be trusted to rule absence out: a Kotlin
platform type originating from Java interop, TypeScript `any`, an `as`
cast, or a non-null assertion (`!`) that overrides the compiler's own
nullability tracking, C#'s null-forgiving `!` operator or
nullable-oblivious legacy code, `unsafe`/cgo/reflection code that steps
outside normal compile-time guarantees, and deserialization of external
data into a typed shape the type system treats as non-null but the source
payload does not guarantee. At these boundaries, reason about what is
actually guaranteed by the runtime or the data source, not what the
declared type alone claims.

### Suppression

Do not report a finding when a guard, early return, assertion, the
language's own type-system guarantee (a genuinely non-nullable type, not
merely the absence of a visible check), a framework or contract guarantee,
or demonstrable upstream validation already makes the value safe at the
point of use. The review question is always whether *this* code path can
actually reach the access with an absent value, not whether the value's
declared type permits absence in the abstract — noisy blanket "this could
be null" findings with no reachable failure path are exactly what this
section does not want. A language that encodes nullability strongly in its
type system (for example, a non-nullable-by-default type system) shifts
review effort toward the escape hatches and interoperability boundaries
above rather than ordinary flow already covered by the compiler.
