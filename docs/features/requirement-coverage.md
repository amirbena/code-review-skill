# Requirement coverage

## What it does

When you supply requirements or acceptance criteria, both review Skills add a
requirement-by-requirement coverage section. Each obligation is reported as
`implemented`, `partially_evidenced`, `not_evidenced`, or `not_applicable`,
with concrete code/test evidence and an overall `complete` or `incomplete`
signal relative to that task.

This is separate from review severity. Missing task coverage becomes a finding
only when it independently meets the normal evidence, scope, and P0/P1/P2
rules; the review decision still depends only on P0/P1 findings.

## Which Skills and when

Both Skills support it. It activates automatically when resolved Review
Context includes authoritative requirements or acceptance criteria. With no
such contract, it is completely inert: no empty section, prompt, signal, or
false finding appears.

## How to invoke it

Supply the contract as review context, for example:

```text
review my local changes against these acceptance criteria:
- validate every write before persistence
- reject writes while the record is locked
```

```text
review PR #812 against GitHub Issue #799
```

A bare Jira or GitHub Issue reference must first resolve through the read-only
context flow described in [Review context](review-context.md).

## Reading the result

Each row cites the originating clause plus the concrete implementation or test
evidence used for its status. Partial or missing coverage names the uncovered
path; ambiguity and non-applicability remain visible instead of being silently
dropped. Status is never based on keyword or embedding similarity.

## Limits

- Only authoritative `requirement` and `acceptance_criteria` context activates
  coverage; discussions and historical notes cannot become a task contract.
- The reviewer does not fetch trackers other than a reference the caller
  explicitly supplied through supported Review Context resolution.
- `not_applicable` may represent an explicitly excluded obligation or one whose
  applicability cannot be resolved from an ambiguous authoritative contract;
  its explanation makes that distinction explicit.

Exact semantics and the machine-readable schema are in
[`shared/policies/requirement-coverage.md`](../../shared/policies/requirement-coverage.md).
