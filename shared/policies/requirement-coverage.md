# Shared Policy — Requirement Coverage

Applies identically to `local-code-review` and `github-pr-review`. When the
caller supplies an authoritative task contract, this policy decomposes it
into independently verifiable requirements and records whether the current
review target evidences each one. It answers "did this change complete the
requested task?" without changing the P0/P1/P2 model or its mechanical
decision.

This policy consumes the authority, conflict, staleness, and ambiguity rules
in [`review-context.md`](review-context.md) and
[`review-evidence.md`](review-evidence.md). Those policies remain the only
owners of which supplied material is authoritative. Requirement coverage
never promotes informational material into a task contract.

## Activation and inert behavior

Activate coverage only when resolved Review Context contains at least one
authoritative `requirement` or `acceptance_criteria` entry. An accepted
decision or repository policy may constrain interpretation, but does not by
itself activate task-completion coverage.

When no activating contract is supplied, emit no coverage model, no
completeness signal, and no coverage-derived finding. Do not ask for a
contract and do not infer one from a branch name, PR title, commit message,
informational discussion, or keyword overlap.

## Requirement decomposition

Preserve source meaning and provenance while splitting the contract into the
smallest independently verifiable obligations. Keep coupled clauses together
when they can only be satisfied as one behavior. Do not rewrite vague prose
into invented pass/fail conditions.

Each requirement receives a stable invocation-local identifier (`R1`, `R2`,
...) in source order. Preserve every authoritative requirement: ambiguity,
conflict, and non-applicability are explicit states, never reasons to drop an
entry.

## Machine-readable model

```yaml
requirement_coverage:
  status: complete | incomplete
  requirements:
    - id: R1
      requirement: <concise source-faithful obligation>
      source:
        type: requirement | acceptance_criteria
        name: <source identifier>
        citation: <clause, checkbox, heading, URL, or supplied-text location>
      status: implemented | partially_evidenced | not_evidenced | not_applicable
      evidence:
        - <code path:line, test name/path:line, or observed validation result>
      explanation: <required concise status justification>
      ambiguity: <optional unresolved ambiguity or authoritative conflict>
```

`status` is `complete` only when every applicable entry is `implemented`,
every `not_applicable` entry has affirmative evidence that it does not apply,
and no entry carries unresolved `ambiguity`. It is `incomplete` when any entry
is `partially_evidenced` or `not_evidenced`, or when unresolved ambiguity
prevents a defensible coverage/applicability conclusion. The four status values
remain unchanged for compatibility: an unresolved applicability question uses
`not_applicable` plus the required `ambiguity` field, but that modifier makes
aggregate coverage incomplete rather than falsely claiming completion.

## Per-requirement status

| Status | Required evidence |
| --- | --- |
| `implemented` | Concrete code/config evidence covers the whole obligation, plus relevant test or observed validation evidence when the behavior is testable. A test name, comment, identifier, or keyword match alone is insufficient. |
| `partially_evidenced` | Concrete evidence proves part of the obligation, but another independently necessary path, condition, or verification is absent or cannot be established. Cite both what is evidenced and the uncovered portion. |
| `not_evidenced` | Inspection found no concrete evidence that the current target implements the obligation, or concrete code/test evidence shows it is missing. State the inspected location or missing path; non-observation without a bounded inspection is insufficient. |
| `not_applicable` | Affirmative evidence establishes that the obligation does not apply to this target, or unresolved ambiguity/conflict prevents a defensible applicability judgment. Cite the basis. The latter case must carry `ambiguity` and makes aggregate coverage incomplete; it is not equivalent to proven non-applicability. |

Every status needs a non-empty explanation. `implemented`,
`partially_evidenced`, and `not_evidenced` need concrete current-target code,
test, configuration, or validation evidence. Context proves what was requested;
it never proves that implementation exists.

## Coverage, findings, and decision are distinct

Coverage is an assessment, not a fourth severity. A missing or partial
requirement produces a P0/P1/P2 finding only when it independently satisfies
[`evidence.md`](evidence.md), [`review-scope.md`](review-scope.md), and
[`severity.md`](severity.md). Its severity comes from actual impact, never
from the coverage status. Conversely, a coverage row may remain incomplete
without a finding when impact or attribution cannot be established.

The review `Decision` remains derived only from finalized P0/P1 findings.
Therefore `Requirement coverage: incomplete` may coexist with `REVIEW CLEAN`;
the output must show both rather than converting incompleteness into an
implicit blocking verdict.

## Worked examples

### Partial implementation

Contract: R1 "validate every write before persistence"; R2 "reject writes
while the record is locked." The diff validates the create path and tests it,
but the update path still writes directly; no lock check exists.

- R1 → `partially_evidenced`: cite the create-path guard/test and the uncovered
  update call.
- R2 → `not_evidenced`: cite the inspected write paths and absence of a lock
  branch/test.
- Overall → `incomplete`.

### Full implementation

The diff routes create and update through the shared pre-write validator,
adds a lock-state rejection, and tests both paths and both outcomes.

- R1 and R2 → `implemented`, each citing its code path and focused tests.
- Overall → `complete`.

### Ambiguous or inapplicable requirement

Contract: "support legacy mode where relevant." The supplied source does not
define legacy mode or which paths are relevant, and no authoritative
clarification settles it.

- R1 → `not_applicable`, with `ambiguity` explaining that applicability cannot
  be decided from the authoritative contract. The entry is retained, not
  silently discarded or upgraded to `implemented`; overall coverage is
  `incomplete` until authoritative evidence resolves applicability.

A genuinely inapplicable requirement—for example, a Windows-only criterion
when the authoritative contract explicitly limits this target to Linux—also
uses `not_applicable`, cites that scope evidence, carries no `ambiguity`, and
does not prevent `complete`.

### No contract

A normal review is invoked with only its local delta or PR. Requirement
coverage is absent from the report and creates no findings; all existing
review behavior is unchanged.

## Output placement

When active, render a concise `Requirement coverage` section after Findings
(or after the change summary when there are no findings) and before
Validation. Show the overall `complete` / `incomplete` signal and every row's
identifier, status, source citation, evidence, and explanation. Machine
consumers may use the YAML-equivalent shape above; human-facing output remains
primary.

This section is a semantic invariant across every supported rendering:
findings or clean, structured or human-style, local or GitHub. Its presentation
may be condensed, but once coverage analysis ran, no output mode may omit the
overall signal or any requirement. When coverage was inert, every mode omits
the section entirely.
