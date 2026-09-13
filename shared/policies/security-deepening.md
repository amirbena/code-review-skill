# Shared Policy — Security Deepening Capability

Applies identically to `local-code-review` and `github-pr-review`, in every
invocation mode. It is a **domain-specific deepening capability** under
[`specialist-depth.md`](specialist-depth.md)'s composition contract: bounded,
evidence-driven investigation of a trust-boundary concern once base review
has already identified, per
[`review-scope.md`](review-scope.md)'s "Security / trust boundaries"
dimension, that a change materially implicates one.

This capability never decides whether a security concern is considered at
all — that is base reasoning's unconditional obligation, owned by
[`review-scope.md`](review-scope.md) and never redefined here. It answers
only the next question, per
[`specialist-depth.md`](specialist-depth.md): given a trust boundary base
reasoning already identified, does the available evidence justify tracing
it further than base reasoning's own bounded pass affords.

## The gap this closes

Base security reasoning ("Security / trust boundaries" in
[`review-scope.md`](review-scope.md)) already asks, for a value crossing
from a less trusted context into a more trusted one, whether the boundary
is still enforced at the point that matters, for every path the base
pass's own bounded investigation reaches. What it cannot always afford on
every change is *exhaustive* tracing: alternate paths into the same
privileged operation, confused-deputy behavior across component
boundaries, whether a validation/sanitization assumption actually holds
everywhere it is relied on, or how a privilege propagates through several
hops. This capability is that deeper pass, engaged only when the evidence
already gathered shows it is warranted.

## Activation

Engages only when both hold:

1. [`review-scope.md`](review-scope.md)'s base pass has already
   identified a materially implicated **Security / trust boundaries**
   dimension (or an authorization/permission-enforcement trigger under
   "Architectural placement and execution-lifecycle fidelity") for the
   current change; and
2. the evidence gathered by that base pass — not the file type, path,
   framework, or a keyword in a name — indicates the boundary's full
   correctness cannot be established within base reasoning's own bounded
   investigation: more than one path can plausibly reach the privileged
   operation, a validation/sanitization step is relied on by code the
   base pass has not yet traced, a privileged operation is invoked
   through more than one caller/component, or the boundary's correctness
   depends on an assumption the base pass could not confirm within its
   own ring.

A change that touches an authentication/authorization module, a
permission check, or a file whose name suggests security relevance does
not by itself satisfy condition 2 — per
[`specialist-depth.md`](specialist-depth.md), those are signals, never
independently sufficient. Conversely, a change with no file conventionally
associated with security can still satisfy both conditions when its
semantic evidence shows a trust-boundary crossing (see worked examples
below).

## Concern areas

Within an activated trust boundary, this capability deepens investigation
of:

- **Authorization placement** — whether the enforcement point is the
  correct one for the operation it guards, not merely present somewhere
  upstream; builds on, and does not duplicate,
  [`review-scope.md`](review-scope.md)'s authorization/permission-
  enforcement trigger under "Architectural placement and execution-
  lifecycle fidelity."
- **Alternate paths to a privileged operation** — every caller/route/
  entry point that can reach the same privileged operation, not only the
  one the diff directly touches, bounded per "Cascading activation"
  below.
- **Confused-deputy behavior** — a component with legitimate elevated
  privilege performing an action on behalf of a less-privileged caller
  without the caller's own authorization being checked at the point the
  privileged action is actually taken.
- **Validation/sanitization assumptions** — whether a value's validation
  or sanitization actually holds at every point it is relied on for
  safety, or only appears to because of where in the flow it happens to
  sit.
- **Privilege propagation** — how a privilege, token, credential, or
  elevated context travels across calls, threads, queues, or process
  boundaries, and whether it can reach a context that should not hold it.
- **Other trust-boundary-adjacent concerns** the activated boundary's own
  evidence surfaces, reasoned about with the same evidence bar as the
  areas above — this list is representative of the capability's scope,
  not an exhaustive checklist run unconditionally on every activation.

## Cascading activation: bounded by the existing expansion contract

Tracing an alternate path or privilege-propagation chain reuses
[`specialist-depth.md`](specialist-depth.md)'s cascading-activation model,
which in turn reuses
[`repository-expansion.md`](repository-expansion.md)'s fixed trigger/ring/
ceiling procedure and
[`review-stopping-criteria.md`](review-stopping-criteria.md)'s stop
conditions — never a separate, unbounded audit of every caller in the
repository. "Insufficient evidence" remains a valid terminal outcome for
a traced path, exactly as it is for base reasoning.

## Findings: ordinary findings, labeled

A finding this capability contributes is an ordinary finding: the same
severity derivation ([`severity.md`](severity.md)), the same evidence bar
([`evidence.md`](evidence.md)), the same identity/deduplication rules, and
the same remediation-scope-boundary reasoning
([`remediation-scope-boundary.md`](remediation-scope-boundary.md)) as any
other finding. It additionally carries the optional `capability` provenance
field, valued `security-deepening`, per
[`finding.md`](../templates/finding.md), "Capability provenance" — never a
severity input, never a second schema. Concrete evidence must be tied to
the actual data/control flow the capability traced; generic
vulnerability-class advice with no traced flow in this change does not
meet the evidence bar and is not reported.

## Worked examples

- **Engages — alternate path to a privileged operation.** A new
  administrative endpoint reuses an existing "delete record" handler.
  Base reasoning identifies the authorization boundary. Evidence shows a
  second, older route also reaches the same handler without the new
  endpoint's added check. This capability traces both paths and reports
  the older route as the missing-enforcement site — the actual defect,
  not the new code that prompted the review.
- **Engages — confused-deputy behavior.** A background worker holds a
  service-level credential and performs an action requested by a
  user-supplied job payload. Base reasoning flags the trust-boundary
  crossing (job payload → privileged worker). This capability traces
  whether the worker re-validates the originating user's own
  authorization before acting, or merely inherits its own elevated
  privilege for whatever the payload requests.
- **Does not engage — bounded base reasoning already suffices.** A
  changed permission check gates a single, directly-called function with
  one caller and no alternate path. Base reasoning confirms the boundary
  is enforced at the point that matters within its own bounded
  investigation; no further tracing is warranted, and this capability
  does not engage.
- **Misleading superficial signal.** A file named `auth_utils.py`
  changes only a logging message format, with no security-relevant
  control or data flow touched. File name alone does not activate this
  capability; base reasoning finds no material trust-boundary signal, and
  this capability does not engage.
- **Implication without the expected file/path.** Application code in an
  unrelated module begins forwarding a user-supplied identifier directly
  into a call that a different, already-privileged component uses to
  select which record to act on — no file conventionally associated with
  "security" or "auth" is touched. Semantic evidence of the trust
  boundary still activates base reasoning and, given the alternate-path
  ambiguity, this capability.
- **Depth vs. remediation scope.** Tracing privilege propagation surfaces
  a legitimate architectural P2: the credential model would ideally be
  redesigned so background workers never hold broader privilege than the
  jobs they run. The finding is reported at its evidenced severity;
  [`remediation-scope-boundary.md`](remediation-scope-boundary.md), not
  the depth of this capability's analysis, governs whether that broader
  redesign is required now or surfaced as a `Follow-up`.

## Non-goals and ownership boundary

- **No external SAST integration.** This capability performs the same
  kind of evidence-based code reasoning as the rest of review — it does
  not invoke, wrap, or depend on an external static-analysis or
  vulnerability-scanning tool.
- **Not a generic security audit or vulnerability scanner.** It never
  runs an unconditional checklist of vulnerability classes against the
  whole repository; it deepens investigation of a trust boundary base
  reasoning already identified as materially implicated by the current
  change, nothing broader.
- **Does not redefine base trust-boundary detection.** Whether a change
  implicates a security/trust-boundary concern at all remains
  [`review-scope.md`](review-scope.md)'s unconditional obligation; this
  capability does not become the mechanism that decides that, and that
  detection does not start existing only once this capability engages.
- **Does not redefine composition, cascading, or remediation-scope
  semantics.** Those remain owned by
  [`specialist-depth.md`](specialist-depth.md),
  [`repository-expansion.md`](repository-expansion.md) /
  [`review-stopping-criteria.md`](review-stopping-criteria.md), and
  [`remediation-scope-boundary.md`](remediation-scope-boundary.md)
  respectively.
- **No new finding/severity/evidence schema.** The `capability`
  provenance field is the only addition, and it is never a severity
  input — see [`finding.md`](../templates/finding.md), "Capability
  provenance."
