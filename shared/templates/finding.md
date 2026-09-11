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
comment by hand.
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
  (`local-code-review` declares none and is unaffected);
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
- `fix` is a direction, never an implemented patch.
