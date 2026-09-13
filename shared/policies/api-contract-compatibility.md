# Shared Policy — API / Contract Compatibility Review

Applies identically to `local-code-review` and `github-pr-review`. It owns
the API/contract compatibility depth owner: recognizing a changed
repository contract, classifying its change shape as compatible / breaking
/ context-dependent, and the fail-closed rule for an unresolvable consumer
surface.

This is a sub-domain of [`review-scope.md`](review-scope.md), which owns
base review scope, the "API / integration contracts" dimension this
capability is one depth owner of, and routes here. It introduces no new
severity, finding category, or evidence standard: every finding still
passes through [`evidence.md`](evidence.md) and
[`severity.md`](severity.md) exactly like any other finding.

## API / contract compatibility review

Signal: the change modifies a repository contract another component
consumes across a boundary that need not be visible as a call site in the
diff — an OpenAPI or JSON Schema document, a protobuf/IDL definition, a
public API request/response model or DTO, an event/message schema, or a
configuration contract read by another service or job. Recognizing the
contract type is a diff-level signal (a schema/IDL file changed, a public
model's field set or type changed, a documented event/message shape
changed); it is never itself the finding.

Base reasoning: classify each changed contract element as **compatible**,
**breaking**, or **context-dependent** by its change shape, reasoned from
existing consumers' actual expectations, never a hypothetical worst case:

- **Additive, optional** (a new optional field/property, a new endpoint or
  message type) — compatible: no existing consumer's expectations change.
- **Field or property removed** — breaking: an existing consumer that
  reads it loses the value outright.
- **Optional narrowed to required** — breaking: it invalidates inputs an
  existing consumer already sends without the new requirement.
- **Property or field renamed** — breaking in both directions: existing
  readers of the old name stop finding it, and existing senders never
  learn the new one.
- **Enum member removed** — breaking: no existing consumer can already
  tolerate a value it has never seen ceasing to exist.
- **Enum member added** — **context-dependent**: additive for a consumer
  that ignores unknown members, breaking for one with an exhaustive
  switch/case or closed-set validation. The diff alone cannot establish
  which kind of consumer exists.
- **Incompatible type change** (a widened or narrowed representation, or
  changed semantics of an existing value) — breaking when it can produce a
  value an existing consumer's prior assumptions do not admit.

Fail-closed on unresolvable consumer intent: when the actual consumer
population, or its tolerance for an additive change like a new enum
member, cannot be established from the diff and any available context,
this pass does not invent a required breaking finding for it — inventing a
breakage claim the diff cannot support is worse than reporting nothing. It
may still surface the ambiguity as an optional, non-blocking note naming
the specific unresolved question, which never raises severity or forces
`CHANGES REQUIRED` on its own. This is the same fail-closed discipline
"Architectural placement and execution-lifecycle fidelity" and "Semantic
change-implication reasoning" in [`review-scope.md`](review-scope.md)
already apply to insufficient evidence, not a new evidence standard
invented for this section alone.

This section adds no new severity, finding category, or probability
score: a breaking-shape finding is labeled confirmed defect / credible
engineering risk per [`evidence.md`](evidence.md) like any other finding,
and classified per [`severity.md`](severity.md) — a consumer-facing
contract break is typically P1. Per [`evidence.md`](evidence.md),
"Findings beyond the changed lines," the search for affected consumers
scales with the change's actual blast radius when the real consumer
surface is broader or narrower than the change alone shows; that scoping
decides whether a break is evidenced at all, never the severity once it
is — blast radius never raises or lowers a finding's severity. The closed
change-shape table above, the recognized
contract types and their diff-recognition detail, and the smallest useful
first implementation are the API/contract compatibility model design
record (a repository-development document, named here, not linked because
it is not a packaged resource).

This is not a second scope model, and it duplicates neither a schema
linter nor a SAST tool: it is one concrete depth owner, for schema/contract
backward compatibility specifically, of the "API / integration contracts"
dimension in [`review-scope.md`](review-scope.md), "Semantic
change-implication reasoning" — alongside, not replacing, "Affected-test /
test-impact analysis" (which traces the change into dependent tests) and
"Architectural placement and execution-lifecycle fidelity"'s
caller/callee-contract trigger (which follows call sites actually present
in the diff's blast radius). This section instead reasons about consumers
that need never appear as a call site at all — an external API client, an
event subscriber, or a configuration reader outside the diff's own
repository. It never fetches or retrieves another repository's consumer
code to resolve that ambiguity; an unresolved consumer surface is exactly
the fail-closed case above, not a reason to expand retrieval.
