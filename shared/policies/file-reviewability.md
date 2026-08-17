# Policy — File Reviewability

Governs how either Code Review Skill evaluates changed files whose direct
line-by-line review may be low-value or impossible. Classification is
evidence-based, using repository instructions, generated-file headers,
`.gitattributes`, build/output paths, nearby generator configuration, and
manifest conventions. Never classify or skip a file by extension alone.

## Scope of applicability (safe short-circuit)

The sections below — Generated files, Vendored dependencies, Manifests
and lockfiles, Minified files and bundles, Binary files, and Snapshots —
each apply only when at least one changed file in the current delta is
evidence-based classifiable into that category (per the classification
rule above: never by extension alone). When no changed file in the delta
matches a given section's category, that section contributes nothing to
this review and may be skipped without walking its checklist. This
narrows which type-specific handling is applied; it never narrows the
Completeness invariant below, which still governs every changed file
regardless of type. All six type-specific sections below are covered by
this same short-circuit — none of them requires being walked when the
delta contains no file evidence-classifiable into it.

## Completeness invariant

Every changed file remains in review scope. A reviewer may choose the most
useful inspection method, but must not silently omit generated, vendored,
minified, binary, snapshot, lock, documentation, manifest, or package-artifact
changes. If content cannot be meaningfully inspected, state the limitation;
do not claim that file or the overall change was fully reviewed.

## Generated files and machine-produced artifacts

Prefer reviewing the canonical source and generator that produced a clearly
generated file. Also inspect the output when it carries material behavior or
risk, including deployment configuration, schemas, API contracts, generated
documentation, or packaged artifacts. An unexpected generated-only change,
an output/source mismatch, or an unexplained artifact is itself review
evidence; generated status is never a blanket exemption.

## Vendored dependencies

For clearly vendored third-party code, avoid pretending the PR author wrote
the implementation or spending review effort on routine line-by-line style.
Instead assess the dependency/version transition, provenance and integrity,
evident licensing or security impact, local patches, and repository policy.
Review authored integration code normally.

## Manifests and lockfiles

Do not ignore lockfiles or machine-generated manifests. Correlate them with
the intended manifest changes and inspect for unexpected dependency growth,
unrelated movement, suspicious sources or integrity changes, and inconsistent
resolution. Avoid meaningless style commentary on generated structure.

## Minified files and bundles

When canonical source exists, review it instead of performing source-style
analysis on minified output, while still checking that the bundle change is
expected and traceable. If only minified output changes unexpectedly, report
that discrepancy or the inability to validate it.

## Binary files

When binary content cannot be inspected meaningfully, inspect change metadata,
provenance, expected source/generation paths, checksums or signatures when
available, and relevant surrounding configuration. State exactly what was not
validated. If an opaque replacement is materially risky and cannot be
verified, report the uncertainty at the severity justified by its impact; do
not call the binary or full review complete.

## Snapshots

Snapshots are behavioral evidence, not automatic noise. Where practical,
confirm that snapshot changes correspond to intended product/test behavior
and nearby source changes. Massive or unexplained snapshot churn requires
investigation rather than automatic acceptance.
