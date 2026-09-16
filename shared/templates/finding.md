# Shared Template — Finding

The canonical shape of a single finding, shared by both Skills' output:
`local-code-review`'s own `templates/local-review-report.md` and
`github-pr-review`'s own `templates/inline-finding.md` /
`templates/external-review-summary.md`. Each Skill renders this shape for
its own delivery surface (a plain-text report, a GitHub inline comment, or
a review-body entry) — the underlying fields and quality contract do not
diverge.

## Contract vs. rendering

```text
review reasoning
    ↓
canonical finding contract   (the fields below — the stable, externally
                              visible shape both Skills and any consuming
                              agent rely on)
    ↓
human/agent-readable rendering (the compact field-oriented blocks in
                                [`finding-rendering.md`](finding-rendering.md),
                                projected onto each delivery surface)
```

The **fields** are the contract. The **rendering** is one projection of
those fields, defined in
[`finding-rendering.md`](finding-rendering.md). The default projection is
the compact, field-oriented block in "Canonical full rendering" — highly
scannable for a human, and predictable enough for a coding agent to parse
and act on. The opt-in concise **human inline rendering** ("Canonical
human inline rendering" there — `github-pr-review` inline surface only,
selected by `human_inline_findings`) is another such projection: it
re-voices an inline finding the way a senior engineer would write the
comment by hand. The opt-in **human full rendering** ("Canonical human
full rendering" there — `github-pr-review` review-body/fallback surface
only, selected directly by `human_review_output`) applies the same
re-voicing to a finding published in full in the body instead of inline,
keeping its `id` and `Location` since the body has no platform-supplied
anchor.
A future additional renderer (for example a machine-readable one) would be
another projection of the same fields; none of these change the finding
fields, the severity model, the evidence bar, the finding's identity, its
canonical location, or the decision derivation. Do not make the
human-facing review a machine-only format.

## Fields

- **id** — a stable finding identifier within the review (e.g. `F1`,
  `F2`), for referencing the same finding across a re-review. Rendered on
  every surface that lists findings for later reference; omitted only on a
  delivery surface that already supplies its own per-finding identity
  (a GitHub inline comment — see "Optional and surface-specific fields");
- **severity** — exactly one of `P0` / `P1` / `P2`, per
  [`../policies/severity.md`](../policies/severity.md), always visible
  first, in the `[P0]` / `[P1]` / `[P2]` form. This is presentation only:
  the P0/P1/P2 definitions, the blocking rule, and the mechanical
  severity → decision derivation are unchanged by this template and are
  owned solely by [`../policies/severity.md`](../policies/severity.md).
  A Skill may additionally render a short, canonical parenthetical next
  to the code (e.g. `P1 (Blocking)`) so a reader unfamiliar with this
  model still sees the meaning at a glance — this is a **per-Skill
  rendering override point**, defined and applied once by that Skill's
  own output policy (`github-pr-review` defines and applies one in its
  own `policies/review-output.md`), never a second, independently
  invented severity model; the bare `[P0]` / `[P1]` / `[P2]` form above
  remains the default for a Skill that declares no such legend
  (`local-code-review` declares none and is unaffected). For
  `github-pr-review`, that parenthetical is itself opt-in, controlled by
  the `include_severity_description` invocation option (default `false`
  — see [`../policies/invocation-options.md`](../policies/invocation-options.md)):
  the bare `[P0]` / `[P1]` / `[P2]` form is this Skill's own default too,
  not only the fallback for a Skill that declares no legend at all;
- **title** — a short, concrete problem statement (what is actually
  wrong — not a vague category like "pagination issue");
- **location** — the finding's **canonical location**: the fix/action
  location, i.e. the most precise place an author must change to resolve
  the finding (file, changed line/range, symbol/function, or narrow
  section). Prefer precision; never invent a location that doesn't exist.
  An unqualified `Location` means this actionable location is resolved
  (the backward-compatible default). It is a semantic property of the
  finding and is never set from where a review platform happens to allow
  a comment — see "Fix/action location, evidence location, publication";
- **evidence location** — optional: where the reviewer observed evidence
  of the problem, when that differs from the resolved fix/action
  location. Rendered only when it adds information (see "Optional and
  surface-specific fields");
- **affected locations** — **conditionally required**: present, and
  required, on every **consolidated root-cause finding** (one finding
  standing in for one shared defect-bearing element that reaches
  **at least two** sites, per
  [`../policies/review-scope.md`](../policies/review-scope.md), "Shared
  root cause versus independent findings"); absent on every ordinary
  single-site finding. It is an **exhaustive** list of the known
  manifestation sites the shared cause reaches — call path, caller, or
  occurrence — each with a one-line note. It never replaces `location`,
  which stays the shared cause / fix-action location; it enumerates the
  blast radius so no affected site is hidden. A consolidated finding
  without it is **not publishable** (see "Finding quality contract" and
  "Affected locations on a consolidated finding");
- **evidence** — the concrete implementation behavior supporting the
  finding, per [`../policies/evidence.md`](../policies/evidence.md) — not
  speculation;
- **impact** — the concrete engineering consequence (incorrect behavior,
  missed review scope, false clean decision, runtime failure, data
  corruption, security exposure, unsafe merge, maintainability
  regression, misleading output, loss of portability, etc.) — this must
  say *why it matters*, not merely restate the title;
- **fix** — a concrete correction direction, not a full patch. The
  reviewer identifies the problem and the direction of the fix; it does
  not implement the fix. This carries the recommended-direction content
  governed by
  [`../policies/remediation-guidance.md`](../policies/remediation-guidance.md);
  that policy still owns what the guidance may and may not say, and this
  rename to a shorter field label never changes it;
- **follow-up** — optional: a broader, legitimately separate concern
  identified alongside this finding whose full remediation is out of the
  current task/PR boundary, per
  [`../policies/remediation-scope-boundary.md`](../policies/remediation-scope-boundary.md).
  Present only when that policy's reasoning lands on "valid concern,
  broader remediation is separate follow-up"; absent when the bounded
  `Fix` is sufficient or when the broader work is itself required (in
  which case it is the `Fix`, not a follow-up). It never carries or
  changes severity, identity, deduplication, or the decision derivation,
  and it is never a substitute for a required `Fix`;
- **runtime validation** — optional: the finding's validation state from a
  targeted runtime check per
  [`../policies/runtime-validation.md`](../policies/runtime-validation.md),
  "Targeted validation of a suspected finding" — one of `runtime-confirmed`
  (a bounded, isolated reproduction confirmed the suspected defect) or
  `attempted-inconclusive` (a reproduction was attempted but was unavailable,
  timed out, unsafe, leaked, or ambiguous). The implicit default `reasoned`
  (no targeted validation attempted or the finding was ineligible) is not
  rendered. It is a provenance annotation, never a severity input: it never
  calculates or changes severity, identity, deduplication, or the decision
  derivation (see "Runtime validation state and provenance");
- **contextual evidence** — optional: the contextual-evidence entries
  (requirement / acceptance criterion / accepted decision / repository
  policy / feedback / historical note / pre-existing-risk note) whose
  provenance informed the finding — recorded when that context is *why the
  finding is attributable to this change*, or is the authoritative evidence
  that a requirement or an approved decision is violated. It is a provenance
  record, not a severity input: it never calculates or changes severity (see
  "Contextual evidence and provenance"). Rendered only when it materially
  explains why the behavior is incorrect or risky (see "Optional and
  surface-specific fields"). This is the finding-side of "Tracing findings
  back to context" in
  [`../policies/review-context.md`](../policies/review-context.md); the typed
  authority and resolution rules for contextual evidence are the
  contextual-evidence model design record (a repository-development document,
  not a packaged resource, so it is named here, not linked).
- **confidence** — the finding's single machine-readable evidence-state
  value: exactly one of `confirmed`, `credible`, `runtime-validation-unavailable`,
  `external-contract-unvalidated`, or `insufficient-context`. It is the one
  epistemic-state field — the `runtime validation` and `contextual evidence`
  fields above are provenance detail that feed it, not independent verdicts.
  The default is `credible` (every reported finding has already cleared the
  evidence bar); it renders in human output only when it is not that default
  and not already implied by a shown `Runtime validation` line (see
  "Confidence and evidence state" for the exact rule).
  A lower value **never** lowers the evidence bar for reporting and never, by
  itself, changes severity, identity, deduplication, or the decision
  derivation (see "Confidence and evidence state"). The closed value set,
  per-value entry criteria, and the mapping from the runtime-validation and
  contextual-evidence states are the finding-confidence model design record
  (a repository-development document, not a packaged resource, so it is named
  here, not linked).
- **capability** — optional: the name of the domain-specific deepening
  capability (per
  [`../policies/specialist-depth.md`](../policies/specialist-depth.md))
  whose deeper reasoning contributed this finding — e.g.
  `security-deepening`. It is a provenance annotation, never a severity
  input: it never calculates or changes severity, identity, deduplication,
  or the decision derivation (see "Capability provenance"). Absent on a
  finding base per-dimension reasoning alone already fully supports, and
  absent when no domain-specific deepening capability engaged.
- **defect_kind** — optional: a short, machine-readable, kebab-case slug
  naming the finding's narrow defect class/mechanism (e.g.
  `sql-injection`, `off-by-one`, `race-condition`,
  `missing-input-validation`, `null-dereference`, `duplicated-logic`) —
  not the title restated, not the file/module, and not the fix
  direction. It is a classification annotation, never a severity input:
  it never calculates or changes severity, identity, deduplication, or
  the decision derivation (see "Defect classification"). Present
  whenever a narrow, well-defined defect class applies to the finding
  (the normal case); absent only when the finding genuinely does not
  reduce to one established or nameable defect class without forcing a
  fit.

## Fix/action location, evidence location, publication

Three things a finding may involve are kept distinct and never collapsed:

1. **Evidence / detection location** — where evidence of the problem was
   observed.
2. **Canonical fix / action location** — where the repository must change
   to resolve the finding. This is the finding's `location` field above,
   and it is pure finding semantics.
3. **Publication anchor** — where a delivery surface (for example, a
   GitHub inline comment) actually places the finding. This is a
   surface constraint owned by each Skill's placement policy, not a
   finding field.

The normal progression is **evidence location → canonical fix/action
location → publication anchor**. A surface that cannot anchor at the
canonical fix/action location changes only where the finding is
published — normally the full finding moves to a review-body / report
section — and never rewrites the `location` value or the finding's
identity.

**No silent promotion.** When evidence is established but an actionable
fix/action location cannot be confidently determined, the finding states
that explicitly rather than presenting the evidence location as the fix
location: `location` carries the best-known coordinate with the trailing
annotation `_(evidence location; fix/action location unresolved)_`, and
`Evidence` still carries the full supporting evidence. An evidence
location is never labeled or consumed as a resolved fix/action location
merely because nothing better was found. The rendered finding always
makes clear what is known, what is unresolved, and what evidence supports
it.

## Deriving the fix/action location

"Fix/action location, evidence location, publication" above distinguishes
the three concepts and how a resolved fix/action location is *published*.
It does not say how that location is *derived* when review evidence,
causal reasoning, or bounded context expansion touch more than one place.
This section owns that derivation — reusing, not redefining, the bounded
caller/callee model in
[`../policies/architectural-placement.md`](../policies/architectural-placement.md)
and the shared-cause model in
[`../policies/root-cause-consolidation.md`](../policies/root-cause-consolidation.md).
It feeds the `location` field above with an already-determined coordinate;
`skills/github-pr-review/policies/finding-placement.md`'s anchor-selection
order then decides where that resolved location is *published* (inline vs.
body, GitHub-commentability, deterministic tie-break) — this section never
re-anchors, and that policy never re-derives.

### Causal center — location follows the claim

An already-accepted finding's claim determines which site owns it, not
proximity, readability, or where the diff happens to be easiest to
annotate:

- when the claim is **about cause** — the site that introduces the
  incorrect state, value, or behavior — anchor there, even when the
  failure is only observed downstream;
- when the claim is **about unsafe handling of an otherwise-valid
  upstream state** — a caller that fails to guard, validate, or recover
  from a condition it is responsible for handling — anchor at that
  downstream handling site, not at the upstream code that produced the
  (valid) state it mishandled.

Prefer the causal/contract-owning site over a downstream manifestation
whenever the claim is about cause; a downstream symptom is evidence of the
defect, not itself the defect's location, unless the claim is specifically
that the downstream site's own handling is unsafe.

**Worked contrast.** A pricing function returns a negative discount for a
malformed coupon (`compute_discount` never clamps a decoded percentage
below `0`), and a caller three frames away renders that negative discount
straight into an invoice total. If the finding's claim is "a malformed
coupon can produce a negative discount," the claim is about *cause* —
`compute_discount` introduces the incorrect value — so the fix/action
location is `compute_discount`, and the invoice-rendering call site is
evidence (how the bad value becomes visible), not the anchor. If instead
the finding's claim is "the invoice renderer trusts an unvalidated
discount and can display a negative total even when the upstream contract
is later hardened," the claim is about *unsafe handling* at the renderer,
so the fix/action location is the renderer itself, and `compute_discount`
is context, not the anchor. The same two pieces of code support two
different, equally valid claims with two different fix/action locations —
the claim, not the code's position in the call chain, decides.

### Caller/callee and contract ownership

There is no mechanical caller/callee preference — a fix/action location is
never assigned merely because a site is "the caller" or "the callee."
Reuse `architectural-placement.md`'s bounded reasoning directly: determine
which side owns the violated responsibility by asking whether the failure
is a **precondition violation** (the caller failed to establish a state
the callee is entitled to assume — anchor at the caller), a **contract
violation** (the callee failed to honor a documented or evidenced
contract regardless of a conforming caller — anchor at the callee), or a
**pre-existing callee bug merely exposed** by a changed caller (the callee
was already broken for that input; the changed caller only reaches it —
anchor at the callee, and treat the caller change as the trigger that
surfaced the evidence, not the cause).

The same reasoning — which side positively owns the violated contract,
established from repository evidence, never from position or naming
alone — extends to every other contract-owning boundary this repository's
shared policies already recognize as a responsibility boundary, per
`architectural-placement.md`'s semantic-risk trigger vocabulary:

- **validation/guard site** — a check that should reject or normalize an
  input before it propagates owns a validation failure, not every site
  that later trips over the un-validated value;
- **state-transition/mutation site** — the code that performs an illegal
  or out-of-order mutation owns a state-consistency defect, not a reader
  that later observes the inconsistent state;
- **lifecycle boundary** — the phase that owns a piece of lifecycle
  bookkeeping (what is recorded as done, attempted, or skipped) owns a
  defect in that bookkeeping, not a downstream phase that trusts it;
- **authorization decision point** — the site that owns the authorization
  decision owns a missing or incorrect check, not a handler that executes
  after an already-wrong decision;
- **encoding/decoding boundary** — the site that owns serialization,
  deserialization, or format translation owns a corruption or
  mismatch introduced there, not every consumer of the resulting value;
- **synchronization/state-assumption boundary** — the site that owns an
  ordering, locking, or shared-state assumption owns a violation of that
  assumption, not every reader that racily observes its effect.

Each of these is resolved the same way `architectural-placement.md`
resolves caller/callee: identify the responsibility boundary from
concrete repository evidence (documented contract, existing enforcement
elsewhere, established lifecycle ordering), then determine which side's
code actually violates it. Naming similarity or structural position is
never itself evidence of ownership, exactly as `architectural-placement.md`
already requires.

### Locality preservation during context expansion

Investigating callers, callees, sibling implementations, tests, shared
utilities, precedent code, or downstream consumers for evidence — per
[`../policies/evidence.md`](../policies/evidence.md),
[`../policies/repository-expansion.md`](../policies/repository-expansion.md),
and `architectural-placement.md`'s own bounded ring-by-ring expansion —
never by itself relocates the finding. Visiting a location for evidence
and anchoring a finding there are different acts: a location becomes the
fix/action anchor only when the causal/contract reasoning above
affirmatively establishes that it owns the claim, not merely because
the review's expansion happened to reach it.

**Worked example.** A review investigates a caching defect and, following
the bounded ring-by-ring model, reads the cache-key builder, two callers,
and an existing test that exercises the stale-key path. The defect turns
out to be in the cache-key builder omitting a tenant identifier. The
caller code and the test were both visited and both contributed evidence
(one caller shows the collision in practice; the test shows the existing
coverage gap), but neither becomes the fix/action location merely from
having been read — the finding still anchors at the cache-key builder,
because that is the site the causal reasoning establishes as the owner.

### Precision versus semantic honesty

Choose the narrowest location that is still semantically honest about
where the defect lives — an exact line, a branch/block, a symbol or
function, or, when the defect is not reducible further, a broader summary
placement (a file, a module boundary, or a described mechanism spanning
several lines). Precision is a quality goal, not a license to
misrepresent: never force false precision at a nearby, easily-commentable
line merely because it is convenient to anchor there or because a review
surface can attach a comment to it. A defect that is genuinely a property
of a function's overall control flow (for example, a missing
state-machine transition that no single line represents) is anchored at
the function or the described mechanism, not arbitrarily pinned to one of
its lines to manufacture a precise-looking anchor.

### Multi-line / multi-file primary selection

When a finding's evidence spans multiple lines or files, select **one**
primary causal/contract-owning location using the reasoning above, and
treat every other touched location as supporting evidence, not as an
additional anchor. This is a single-finding selection rule, not a second
consolidation mechanism: reuse
[`../policies/root-cause-consolidation.md`](../policies/root-cause-consolidation.md)'s
affected-locations model only when that policy's shared-cause bar is
actually met (one defect-bearing element whose single incorrectness
reaches at least two manifestation sites) — and when it is met, this
section's primary-location reasoning is exactly what selects which of
those sites is the shared cause that becomes `location`, while the rest
populate `affected locations`. A finding that merely touches several
files without a positively established shared cause still gets one
primary location chosen by causal/contract ownership; it does not become
a consolidated finding, and it does not get several competing anchors.

### Test versus production placement

Evidence appearing in a test file never automatically makes the test the
fix/action location:

- a **test that reveals a genuine production defect** anchors at the
  production code the test exposes — the test is evidence (it is how the
  defect became visible), not the anchor;
- a **defective test itself** — one asserting an incorrect expectation,
  missing coverage for a case it should exercise, or resting on a broken
  fixture — anchors at the test, because the test is the thing that must
  change;
- a **sibling or precedent implementation that merely demonstrates
  correct behavior** (used, for example, to show how an analogous case is
  handled correctly elsewhere) is evidence supporting the finding's claim
  about the defective location; it is never itself the anchor, because it
  is not the thing that must change.

### Location ambiguity

When more than one location remains plausible after the reasoning above,
rank candidates in this fixed order and select the highest-ranked
plausible one:

1. **causal ownership** — the site establishing the causal reasoning above
   confirms actually introduces the incorrect state or behavior;
2. **contract ownership** — the site the caller/callee-and-contract-
   ownership reasoning above confirms owns the violated responsibility,
   when causal ownership alone does not resolve it;
3. **actionable repair site** — the narrowest location where a concrete,
   scoped correction can actually be made, when neither of the above
   fully resolves the ambiguity;
4. **precise-but-still-honest changed location** — the most specific
   changed location that remains semantically honest per "Precision
   versus semantic honesty" above, as a last-resort tie-break among
   otherwise-equal candidates.

When ambiguity remains even after this ranking — the evidence does not
let any candidate clear the bar above — do not invent certainty. Use
"Fix/action location, evidence location, publication"'s existing
unresolved state: `location` carries the best-known evidence coordinate
with the trailing `_(evidence location; fix/action location unresolved)_`
annotation, exactly as for any other unresolved fix/action location.

## Affected locations on a consolidated finding

A **consolidated root-cause finding** represents one shared defect-bearing
element whose single incorrectness reaches **at least two** sites (see
[`../policies/review-scope.md`](../policies/review-scope.md), "The
authoritative consolidated finding"). It keeps the normal single `id`,
severity, evidence, and fix; its `location` is the shared cause. It
additionally carries an **affected locations** list:

- the list is **required** on such a finding and part of its mandatory core
  (see "Finding quality contract"): a consolidated finding rendered without
  it, or with fewer than two entries, is not publishable;
- it is **exhaustive for the manifestation sites the review found** — every
  one is named (call path, caller, or occurrence) with a short note on how
  the shared cause reaches it. `Evidence` may walk through a representative
  subset; this list carries the complete known blast radius;
- it is rendered on **every** surface that renders the finding — the full
  rendering, the GitHub inline surface, the human inline voice, and the
  summary-pointer form — so an affected site is never dropped from a
  human-readable or a structured projection;
- it does not change the finding's identity, severity, evidence bar,
  canonical `location`, or the mechanical decision derivation. It is the
  blast-radius enumeration the root-cause pass already requires, given one
  stable field.

An ordinary finding that names a single site does not get this field, and
the field is never used to pack unrelated findings into one entry — that is
the over-merge "Fail open toward separate findings" in
[`../policies/review-scope.md`](../policies/review-scope.md) forbids.

## Contextual evidence and provenance

A finding is always attributable to **code evidence** — the concrete
implementation behavior in its `Evidence` field, per
[`../policies/evidence.md`](../policies/evidence.md). It may additionally
carry **provenance**: the optional **contextual evidence** field lists the
caller-supplied contextual-evidence entries that informed it — a
requirement, an acceptance criterion, an accepted decision, a repository
policy, prior implementation feedback, a historical note, or a
pre-existing-risk note. This is the finding-side of "Tracing findings back
to context" in
[`../policies/review-context.md`](../policies/review-context.md), given one
stable field; the typed authority of each source and the rules for
conflicting, stale, ambiguous, or non-authoritative context are owned by the
contextual-evidence model design record (a repository-development document,
named here rather than linked because it is not a packaged resource).

- **Optional and evidence-gated.** It renders only when the contextual
  evidence materially explains why the behavior is incorrect or risky — not
  on every finding, and never as a second, duplicate listing of the finding.
  When it adds nothing it is absent, like every other optional field.
- **Provenance is not a severity input.** Authoritative contextual evidence
  may supply the evidence that a requirement or an approved decision is
  violated, and that established violation feeds the finding's
  independently derived severity per
  [`../policies/severity.md`](../policies/severity.md) exactly as any code
  evidence would. The provenance annotation **itself** never calculates,
  raises, lowers, or overrides severity, and never changes the finding's
  identity, its deduplication, or the mechanical decision derivation.
  Severity is never inherited from a context source's own wording or
  emphasis.
- **The epistemic roll-up is `confidence`.** This field lists *which context
  informed the finding*; how sure the reviewer is is expressed once, in
  `confidence` (see "Confidence and evidence state"). An authoritative source
  that proves a violation the code exhibits contributes `confirmed`; an
  unresolved authoritative question contributes `insufficient-context`;
  informational context contributes nothing.
- **Surface rendering.** On the full rendering it is its own line; on the
  GitHub inline surface it folds into `evidence` prose (the same treatment
  as `evidence location`). See
  [`finding-rendering.md`](finding-rendering.md).

## Runtime validation state and provenance

A finding may additionally carry a **runtime validation** state produced by a
targeted, isolated reproduction per
[`../policies/runtime-validation.md`](../policies/runtime-validation.md),
"Targeted validation of a suspected finding". It is a second kind of
provenance, orthogonal to contextual evidence:

- **Three states, one always applies.** `reasoned` (the default — no targeted
  validation was attempted or the finding was ineligible; static evidence
  alone), `runtime-confirmed` (a bounded reproduction ran inside the required
  execution boundary and its pass/fail evidence confirmed the suspected
  defect), or `attempted-inconclusive` (a reproduction was attempted but the
  boundary was unavailable or unverifiable, the run exceeded its budget, it
  could not be made safe, its generated artifact could not be shown to stay
  out of the working tree, or the result was ambiguous).
- **Static evidence stays sufficient.** `reasoned` and
  `attempted-inconclusive` findings are complete on their `Evidence` field
  alone; a missing, unavailable, or inconclusive targeted run never blocks,
  downgrades, or weakens a finding.
- **Provenance, not a severity input.** The state never calculates, raises,
  lowers, or overrides the severity derived from impact per
  [`../policies/severity.md`](../policies/severity.md), and never changes the
  finding's identity, its deduplication, or the mechanical decision
  derivation. `runtime-confirmed` does not escalate a P2;
  `attempted-inconclusive` does not de-escalate a P1.
- **A disproved suspicion is not a finding.** When a targeted run shows the
  code behaves correctly, no finding is raised for that suspicion; the run
  and its pass evidence are recorded in the review's `Validation` section,
  not as a finding.
- **Surface rendering.** Rendered only when the state is `runtime-confirmed`
  or `attempted-inconclusive` (the `reasoned` default is never rendered, like
  every other absent optional field). On the full rendering it is its own
  line; on the GitHub inline surface it folds into `evidence` prose. See
  [`finding-rendering.md`](finding-rendering.md).
- **The epistemic roll-up is `confidence`.** This field records *what
  targeted reproduction ran and its result*; the finding's single
  machine-readable evidence-state value is `confidence` (see "Confidence and
  evidence state"), into which `runtime-confirmed` maps as `confirmed` and
  `attempted-inconclusive` maps as `runtime-validation-unavailable`. The two
  fields never disagree — one is the runtime detail, the other the unified
  state.

## Confidence and evidence state

Every finding carries exactly one **confidence** value — the single
machine-readable field that says how sure the reviewer is that the defect is
real. It is a small closed set of named states, never a probability score or
an "AI confidence %".

- **The closed value set.** `confirmed` (the evidence directly demonstrates
  the incorrect behavior — a `runtime-confirmed` targeted run, direct static
  proof, or an authoritative context source that proves a violation the code
  exhibits); `credible` (a plausible failure mode with concrete evidence but
  not directly demonstrated — the default and the floor); `runtime-validation-unavailable`
  (an eligible targeted run was attempted and came back `attempted-inconclusive`);
  `external-contract-unvalidated` (credible on the code in view, but
  correctness turns on an external contract the reviewer could not inspect
  within the review boundary); `insufficient-context` (concrete code evidence
  of a problem, but a bounded, material piece of caller context needed to
  characterize it was missing — the `REPORT_AMBIGUITY` case). The per-value
  entry criteria and the deterministic derivation order are the
  finding-confidence model design record (a repository-development document,
  named here, not linked because it is not a packaged resource).
- **One field, not three.** `runtime validation` and `contextual evidence`
  above are provenance detail — *what ran*, *what informed the finding*. The
  epistemic verdict is expressed once, here. `runtime-confirmed` →
  `confirmed`; `attempted-inconclusive` → `runtime-validation-unavailable`;
  an authoritative context source that proves a violation → `confirmed`; an
  unresolved authoritative context question → `insufficient-context`;
  informational context contributes nothing. The fields never contradict
  each other.
- **Default.** When a Skill does not compute confidence, the value is
  `credible`. Every reported finding has already met the evidence bar in
  [`../policies/evidence.md`](../policies/evidence.md), so `credible` asserts
  exactly what reporting the finding already asserts. A finding is never
  emitted with an absent or unknown confidence.
- **It never lowers the bar, the severity, or the decision.** A value below
  `confirmed` is an annotation on a finding that has *already* cleared the
  evidence bar — it is never a licence to report one that has not, and
  `insufficient-context` in particular never turns a speculative hunch into a
  reportable finding. `confidence` never calculates, raises, lowers, or
  overrides the P0/P1/P2 severity per
  [`../policies/severity.md`](../policies/severity.md); `confirmed` does not
  escalate a P2 and the three open-question values do not de-escalate a P1 or
  suppress a finding. The mechanical decision derivation never reads
  `confidence`. It never changes a finding's identity or deduplication.
- **Surface rendering.** Rendered only when the value is **not** the
  `credible` default (the same rule every other optional field follows),
  **and** omitted from human output when it would only repeat a `Runtime
  validation` line already shown on the finding — a `runtime-confirmed` line
  present alongside `confidence` `confirmed`, or an `attempted-inconclusive`
  line alongside `confidence` `runtime-validation-unavailable`. It still
  renders when the value adds something that line does not: a `confirmed`
  established by static or contextual evidence, `external-contract-unvalidated`,
  or `insufficient-context`. On the full rendering it is its own line after
  `Evidence` (and after any `Runtime validation` line); on the GitHub inline
  surface it folds into `evidence` prose. See
  [`finding-rendering.md`](finding-rendering.md). The **machine-readable
  output always carries `confidence`**, regardless of this human-surface
  suppression.

## Capability provenance

A finding may additionally name the **domain-specific deepening
capability** (per
[`../policies/specialist-depth.md`](../policies/specialist-depth.md))
whose deeper reasoning contributed it — for example
`security-deepening`. This is a third kind of provenance, alongside
`contextual evidence` and `runtime validation`: it records *which
capability's reasoning produced the finding*, not how sure the reviewer
is (that stays `confidence`'s job) and not what informed it (that stays
`contextual evidence`'s job).

- **Optional, and only when a capability actually contributed.** Absent
  on every finding base per-dimension reasoning
  ([`../policies/review-scope.md`](../policies/review-scope.md),
  "Semantic change-implication reasoning") already fully supports on its
  own, and absent whenever no domain-specific deepening capability
  engaged for this review. A capability that engages but finds nothing
  beyond what base reasoning already established contributes no finding
  merely to prove it ran, per
  [`specialist-depth.md`](../policies/specialist-depth.md), "Capability-
  contributed findings are labeled, not re-schemed."
- **Provenance is not a severity input.** It never calculates, raises,
  lowers, or overrides the severity derived from impact per
  [`../policies/severity.md`](../policies/severity.md), and never changes
  the finding's identity, its deduplication, or the mechanical decision
  derivation. A capability-contributed finding is evaluated exactly like
  any other finding.
- **Does not replace `confidence`.** Which capability contributed a
  finding says nothing about how sure the reviewer is that the defect is
  real; a capability-contributed finding still carries its own
  independently derived `confidence` value.
- **Composability.** When more than one capability's reasoning
  contributed to the same finding (for example, a cascading activation
  per [`specialist-depth.md`](../policies/specialist-depth.md),
  "Cascading activation"), list each contributing capability; this never
  fragments the finding into multiple entries for the same underlying
  defect.
- **Surface rendering.** Rendered only when present (the same rule every
  other optional field follows). On the full rendering it is its own
  line after `Evidence` and any `Contextual evidence` / `Runtime
  validation` / `Confidence` lines; on the GitHub inline surface it
  folds into `evidence` prose — there is no separate `Capability:` line
  on that surface. See [`finding-rendering.md`](finding-rendering.md).

## Defect classification

A finding may additionally carry a **defect_kind**: a short,
machine-readable slug naming the narrow defect class/mechanism the
finding represents — for example `sql-injection`, `off-by-one`,
`race-condition`, `missing-input-validation`, `null-dereference`, or
`duplicated-logic`. It is a classification, not a fourth kind of
provenance: unlike `contextual evidence`, `runtime validation`, and
`capability`, it does not record *what informed* or *validated* the
finding — it names *what kind of defect* the finding is, on top of the
free-text `title` / `evidence` / `impact` that already describe it.

- **A slug, not a sentence.** Lowercase kebab-case, naming the defect's
  mechanism/category — never the file or symbol, never a restatement of
  `title`, and never the fix direction. Prefer the most specific
  well-established term for the defect's class over inventing a novel
  phrase for a familiar defect class (a `race-condition` stays
  `race-condition`, not `bad-concurrency-handling`), so independently
  authored slugs for the same defect class tend to agree; a genuinely
  novel or repository-specific defect class still gets a concise slug of
  its own rather than being forced into an unrelated established term.
  This is a naming convention, not an enumerated closed vocabulary — a
  repository-development consumer of this classification (a benchmark
  harness's defect-class-equality matching, a repository-development
  document, not a packaged resource) documents worked examples of the
  convention but does not restrict the slug set.
- **Not a severity or identity input.** It never calculates, raises,
  lowers, or overrides severity, and never changes the finding's
  identity, its deduplication, or the mechanical decision derivation —
  exactly like `contextual evidence`, `runtime validation`,
  `confidence`, and `capability`.
- **Present whenever it cleanly applies.** Unlike the provenance fields
  above (present only when something actually informed, validated, or
  deepened the finding), a `defect_kind` slug applies to almost every
  finding — a narrow defect class is normally identifiable from the
  finding's own evidence. Absent only when the finding genuinely does
  not reduce to one established or nameable defect class without
  forcing a fit (for example, several unrelated style nits grouped only
  by file).
- **Surface rendering.** Rendered when present (the same rule every
  other optional field follows). On the full rendering it is its own
  line after `Evidence` and before any `Contextual evidence` / `Runtime
  validation` / `Confidence` / `Capability` lines; on the GitHub inline
  surface it folds into `evidence` prose — there is no separate `Defect
  kind:` line on that surface. See
  [`finding-rendering.md`](finding-rendering.md).

## Finding quality contract

Every finding must independently answer: **What? Where? Evidence?
Impact? Fix?** A finding is not publishable until all five are present
(on a surface that supplies its own location, "Where" is supplied by that
surface — see "Optional and surface-specific fields"). Do not present a
finding as factual without evidence sufficient to support it; label
genuine uncertainty as such rather than asserting it as a confirmed
defect (see [`../policies/evidence.md`](../policies/evidence.md)).

This is the mandatory core. It is never reduced to hit a length target,
and concision (below) never removes any of it.

**Consolidated root-cause findings** carry one addition to the mandatory
core: the **affected locations** list (see "Affected locations on a
consolidated finding"). A finding that consolidates one shared cause across
several sites is not publishable without an exhaustive affected-locations
list of at least two known manifestation sites. Ordinary single-site
findings do not carry the field and are unaffected by this clause.

## Conciseness contract

A normal finding is **field-oriented and concise by default** — a block a
reader absorbs at a glance, not a multi-paragraph essay:

- each rendered field is normally one or two sentences — a direct
  statement, not a paragraph;
- the fields carry the substance; there is no separate narrative
  wrapper around them;
- concision comes from cutting restatement, hedging, and background — never
  from dropping evidence, weakening it to a vague gesture ("this could be
  better"), or omitting impact or fix;
- there is no line-count target. If a field genuinely cannot be stated
  concisely *and* completely, that is the signal the finding qualifies for
  the longer-explanation exception below — not a licence to truncate
  substance.

## When a longer explanation is justified

Some findings legitimately need more than one or two sentences of
explanation for the evidence or impact to be understood at all. This is a
**controlled exception**, not the default, and applies only when the
finding is one of:

- **non-obvious cross-file / cross-module behavior** — the defect only
  makes sense once the interaction between two or more separated pieces of
  code is spelled out;
- **a concurrency, ordering, or race condition** — the failure depends on
  interleaving, timing, or execution order that must be walked through;
- **a security implication** — a short threat description is needed to
  show how the weakness is reached or exploited, and why it matters;
- **a complex invariant violation** — the invariant, where it is
  established, and how the change breaks it need stating together;
- **evidence that cannot be understood without brief context** — a small
  amount of surrounding behavior must be described for the concrete
  evidence to mean anything.

When one of these applies, render the extra explanation in a single
optional **Details** field (see below), kept as tight as the case allows
— a short paragraph, still not an open-ended essay. The `Evidence`,
`Impact`, and `Fix` fields stay concise; `Details` carries the reasoning
that genuinely needs room. A finding outside the categories above does
not get a `Details` field, and an ordinary finding is never padded into
one.

## Optional and surface-specific fields

Optional fields appear **only when they add information**. An empty or
placeholder field is never rendered — no `Location:` line with nothing
after it, no `Details:` heading with boilerplate under it.

- **evidence location** — the evidence / detection location from
  "Fix/action location, evidence location, publication" when it differs
  from the resolved fix/action `location`. On the full rendering it is
  its own line directly after `Location` (see
  [`finding-rendering.md`](finding-rendering.md), "Canonical full
  rendering"); on a surface that already supplies the anchor (a GitHub
  inline comment) it is folded into `evidence` prose instead. Absent
  when it coincides with `location` or adds nothing;
- **follow-up** — the broader, separately-scoped remediation recommendation
  from
  [`../policies/remediation-scope-boundary.md`](../policies/remediation-scope-boundary.md).
  Rendered only when that policy identifies such a concern; on the full
  rendering it is its own line after `Fix`, on the GitHub inline surface it
  folds into `fix` prose as a clearly separated closing sentence rather
  than a distinct field. It never reads as part of the required fix and
  never carries or changes a severity;
- **details** — the longer explanation permitted by "When a longer
  explanation is justified" above. Visibility follows
  [`../policies/invocation-options.md`](../policies/invocation-options.md),
  "Finding-detail precedence"; absent when not populated or not selected;
- **contextual evidence** — the provenance entries that informed the finding
  (see "Contextual evidence and provenance"). Rendered only when the
  contextual evidence materially explains why the behavior is incorrect or
  risky; on the full rendering it is its own line, on the GitHub inline
  surface it folds into `evidence` prose. Absent on a finding that rests on
  code evidence alone. It never carries or changes a severity;
- **runtime validation** — the finding's targeted-validation state (see
  "Runtime validation state and provenance"). Rendered only when it is
  `runtime-confirmed` or `attempted-inconclusive`; the `reasoned` default is
  never rendered. On the full rendering it is its own line, on the GitHub
  inline surface it folds into `evidence` prose. It never carries or changes
  a severity, identity, deduplication, or the decision derivation;
- **confidence** — the finding's unified evidence-state value (see
  "Confidence and evidence state"). Rendered only when it is **not** the
  `credible` default **and** it is not already implied by a shown `Runtime
  validation` line (see that section for the suppression rule). On the full
  rendering it is its own line after `Evidence` (after any `Runtime
  validation` line), on the GitHub inline surface it folds into `evidence`
  prose. It never lowers the evidence bar and never carries or changes a
  severity, identity, deduplication, or the decision derivation; the
  machine-readable schema always carries it regardless of the human-surface
  suppression;
- **affected locations** — the manifestation-site list of a consolidated
  root-cause finding. It is **not optional**: on a consolidated finding it
  is required and part of the mandatory core ("Finding quality contract"
  and "Affected locations on a consolidated finding"); on any other finding
  it is absent. It is listed here only for its **surface-specific
  rendering**: unlike the other entries in this section it is never
  suppressed, it renders on every surface, and on the GitHub inline surface
  it is folded into the prose rather than shown as its own field;
- **capability** — the domain-specific deepening capability whose
  reasoning contributed the finding (see "Capability provenance").
  Rendered only when a capability actually contributed; on the full
  rendering it is its own line after `Evidence` (and after any
  `Contextual evidence` / `Runtime validation` / `Confidence` lines), on
  the GitHub inline surface it folds into `evidence` prose. It never
  carries or changes a severity, identity, deduplication, or the
  decision derivation;
- **defect_kind** — the narrow defect-class slug from "Defect
  classification". Rendered whenever a narrow, well-defined defect class
  applies to the finding; on the full rendering it is its own line after
  `Evidence` and before any `Contextual evidence` / `Runtime validation`
  / `Confidence` / `Capability` line, on the GitHub inline surface it
  folds into `evidence` prose. It never carries or changes a severity,
  identity, deduplication, or the decision derivation;
- **source annotation on `location`** — a Skill may append a short
  parenthetical after the location value when it has its own concept that
  classifies *where the finding's evidence came from* within that Skill's
  source-state model (see [`finding-rendering.md`](finding-rendering.md),
  "Location source annotation"). Present
  only for a Skill that has such a concept;
- **implementation prompt** — `local-code-review` only, and only under its
  explicit `include_fix_prompt` opt-in, appended after `Fix` and before
  supporting `Details` when present for a
  qualifying finding. Never rendered by `github-pr-review`, never rendered
  when the flag is off, and never rendered for a clean review. Owned by
  that Skill's `templates/local-review-report.md` and the shared
  [`../policies/remediation-guidance.md`](../policies/remediation-guidance.md);
- **id** and **location** are part of the mandatory core on a surface that
  needs them, but are **omitted on a GitHub inline comment**: GitHub
  supplies the file/line from the comment anchor and its own comment
  identity, so repeating them as `id:` / `Location:` fields is redundant.
  Every other surface renders both.

The mandatory core of a normal actionable finding —
`id` (where the surface needs it), `severity`, `title`, `location` (where
the surface needs it), `evidence`, `impact`, `fix` — is always present and
deterministically identifiable, so an agent can rely on it. The human-first
projection orders content as problem (`Evidence`) → consequence (`Impact`) →
correction (`Fix`) → optional supporting technical detail (`Details`).

## Canonical renderings

The concrete rendering exemplars — the compact full rendering, the GitHub
inline rendering, the opt-in human inline re-voicing, and the
summary-pointer form — live in
[`finding-rendering.md`](finding-rendering.md). They are projections of the
fields and quality contract above; they never change the finding's
identity, severity, evidence bar, canonical location, or the decision
derivation.

## Rules

These are the finding-field and quality-contract rules. The
rendering-specific rules are in
[`finding-rendering.md`](finding-rendering.md), "Rules".

- one severity per finding, always visible first;
- the mandatory core (`What? Where? Evidence? Impact? Fix?`) is always
  present per "Finding quality contract"; concision never removes any of
  it;
- fields are concise by default per "Conciseness contract"; a longer
  `Details` field is allowed only for a finding in one of the categories
  in "When a longer explanation is justified" and rendered only per the
  detail-precedence rule in `invocation-options.md`;
- a **consolidated root-cause finding** additionally carries an **affected
  locations** list — required, part of the mandatory core, exhaustive for
  the known sites, and at least two entries; it is not an optional field,
  it renders on every surface, and it never replaces `location` (see
  "Finding quality contract" and "Affected locations on a consolidated
  finding"). An ordinary single-site finding never carries it;
- evidence-based — no generic "this could be improved" without a
  concrete basis;
- impact is explicit and distinct from the title — it explains
  consequence, not just restates the defect;
- no duplicate findings for the same underlying issue;
- `location` is the canonical fix/action location and is never derived
  from where a platform allows a comment; an `evidence location` renders
  only when it differs from `location` and adds information (see
  "Fix/action location, evidence location, publication");
- an evidence location is never relabeled as a resolved fix/action
  location — an unresolved fix/action location is stated explicitly with
  the trailing annotation;
- the optional **contextual evidence** field records the provenance that
  informed a finding; it renders only when it materially explains the
  problem, never carries or changes a severity, and never alters the
  finding's identity, deduplication, or decision derivation (see "Contextual
  evidence and provenance");
- the optional **runtime validation** field records the finding's
  targeted-validation state (`reasoned` / `runtime-confirmed` /
  `attempted-inconclusive`); it renders only for the two non-default states,
  a `reasoned` or inconclusive finding is complete on static evidence alone,
  and the state never carries or changes a severity, identity, deduplication,
  or decision derivation (see "Runtime validation state and provenance");
- the **confidence** field records the finding's one unified evidence-state
  value (`confirmed` / `credible` / `runtime-validation-unavailable` /
  `external-contract-unvalidated` / `insufficient-context`), rolling up the
  runtime-validation and contextual-evidence provenance into a single
  machine-readable state; it defaults to `credible`, renders in human output
  only when it is not that default and not already implied by a shown
  `Runtime validation` line, never lowers the evidence bar for reporting, and
  never by itself changes severity, identity, deduplication, or the decision
  derivation (see "Confidence and evidence state");
- the optional **capability** field names the domain-specific deepening
  capability whose reasoning contributed a finding; it renders only when
  a capability actually contributed, and it never carries or changes a
  severity, identity, deduplication, or decision derivation (see
  "Capability provenance");
- the optional **defect_kind** field names the finding's narrow
  defect-class slug (see "Defect classification"); it renders whenever a
  well-defined defect class applies to the finding, and it never carries
  or changes a severity, identity, deduplication, or decision derivation;
- `fix` is a direction, never an implemented patch.
