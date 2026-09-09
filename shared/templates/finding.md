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
human/agent-readable rendering (the compact field-oriented block below,
                                projected onto each delivery surface)
```

The **fields** are the contract. The **rendering** is one projection of
those fields. The default projection is the compact, field-oriented block
in "Canonical full rendering" — highly scannable for a human, and
predictable enough for a coding agent to parse and act on. The opt-in
concise **human inline rendering** ("Canonical human inline rendering"
below — `github-pr-review` inline surface only, selected by
`human_inline_findings`) is another such projection: it re-voices an
inline finding the way a senior engineer would write the comment by hand.
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
  owned solely by [`../policies/severity.md`](../policies/severity.md);
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
- **affected locations** — required on a **consolidated root-cause
  finding** (one finding standing in for one shared defect-bearing element
  that reaches multiple sites, per
  [`../policies/review-scope.md`](../policies/review-scope.md), "Shared
  root cause versus independent findings"): a list naming every
  manifestation site the shared cause reaches — call path, caller, or
  occurrence — each with a one-line note. It never replaces `location`,
  which stays the shared cause / fix-action location; it enumerates the
  blast radius so no affected site is hidden. Absent on an ordinary
  single-site finding (see "Affected locations on a consolidated
  finding");
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
  rename to a shorter field label never changes it.

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
element whose single incorrectness reaches several sites (see
[`../policies/review-scope.md`](../policies/review-scope.md), "The
authoritative consolidated finding"). It keeps the normal single `id`,
severity, evidence, and fix; its `location` is the shared cause. It
additionally carries an **affected locations** list:

- every manifestation site is named — call path, caller, or occurrence —
  with a short note on how the shared cause reaches it;
- the list is rendered on **every** surface that renders the finding — the
  full rendering, the GitHub inline surface, the human inline voice, and
  the summary-pointer form — so an affected site is never dropped from a
  human-readable or a structured projection;
- it does not change the finding's identity, severity, evidence bar,
  canonical `location`, or the mechanical decision derivation. It is the
  blast-radius enumeration the root-cause pass already requires, given one
  stable field.

An ordinary finding that names a single site does not get this field, and
the field is never used to pack unrelated findings into one entry — that is
the over-merge "Fail open toward separate findings" in
[`../policies/review-scope.md`](../policies/review-scope.md) forbids.

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
  its own line directly after `Location` (see "Canonical full
  rendering"); on a surface that already supplies the anchor (a GitHub
  inline comment) it is folded into `evidence` prose instead. Absent
  when it coincides with `location` or adds nothing;
- **details** — the longer explanation permitted by "When a longer
  explanation is justified" above. Visibility follows
  [`../policies/invocation-options.md`](../policies/invocation-options.md),
  "Finding-detail precedence"; absent when not populated or not selected;
- **affected locations** — the manifestation-site list of a consolidated
  root-cause finding (see "Affected locations on a consolidated finding").
  Present only on such a finding; when present it renders on every
  surface, unlike the other entries here it is not suppressed on the
  inline surface — it is folded into the prose there;
- **source annotation on `location`** — a Skill may append a short
  parenthetical after the location value when it has its own concept that
  classifies *where the finding's evidence came from* within that Skill's
  source-state model (see "Location source annotation" below). Present
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

## Canonical full rendering

Used wherever a finding needs its complete, standalone representation —
a local review report, or a GitHub review body when no valid inline
anchor exists. Compact and field-oriented:

```markdown
### <id> [<severity>] <short, concrete title>

- **Location:** `<path>:<line-or-range>`
- **Evidence:** <concrete evidence, concise>
- **Impact:** <concrete engineering consequence, concise>
- **Fix:** <concrete correction direction, not a patch>
```

A finding that meets "When a longer explanation is justified" and whose
detail-visibility decision is true adds one `Details` field after `Fix`:

```markdown
### <id> [<severity>] <short, concrete title>

- **Location:** `<path>:<line-or-range>`
- **Evidence:** <concrete evidence, concise>
- **Impact:** <concrete engineering consequence, concise>
- **Fix:** <concrete correction direction, not a patch>
- **Details:** <the cross-file / concurrency / security / invariant
  explanation supporting the finding — a short paragraph, not an essay>
```

When the evidence was observed somewhere other than the resolved
fix/action location, one `Evidence location` line is added directly after
`Location` (omitted when the two coincide):

```markdown
### <id> [<severity>] <short, concrete title>

- **Location:** `<fix/action path>:<line-or-range>`
- **Evidence location:** `<where the evidence was observed>`
- **Evidence:** <concrete evidence, concise>
- **Impact:** <concrete engineering consequence, concise>
- **Fix:** <concrete correction direction, not a patch>
```

When the fix/action location is unresolved, no `Evidence location` line
is added; `Location` instead carries the best-known coordinate with the
trailing unresolved annotation (see "Fix/action location, evidence
location, publication"):

```markdown
- **Location:** `<observed path>:<line-or-range>` _(evidence location; fix/action location unresolved)_
```

A **consolidated root-cause finding** adds an `Affected locations` list
directly after `Location` (see "Affected locations on a consolidated
finding"); `Location` is the shared cause:

```markdown
### <id> [<severity>] <short, concrete title>

- **Location:** `<shared-cause path>:<line-or-range>`
- **Affected locations:**
  - `<path>:<line-or-range>` — <how the shared cause reaches this site>
  - `<path>:<line-or-range>` — <how the shared cause reaches this site>
- **Evidence:** <the shared cause, concise>
- **Impact:** <combined engineering consequence across the affected sites>
- **Fix:** <one correction direction at the shared cause / canonical owner>
```

### Location source annotation

When a Skill appends its source-state classification, it goes after the
required `` `<path>:<line-or-range>` `` value on the `Location` line, as a
strict trailing addition — it never replaces, reorders, or hides that
value:

```markdown
- **Location:** `<path>:<line-or-range>` _(<annotation>)_
```

For example, `local-code-review` appends the repository-state category a
finding was attributed to (`(committed)`, `(staged)`, `(unstaged)`, or
`(untracked)`) — see that Skill's own `policies/repository-state.md`,
"Attribution in findings" (not linked from here: this shared template is
packaged standalone into every consuming Skill's own archive, and must
never depend on another Skill's directory existing alongside it). This
concept is specific to a local Git working tree and has no equivalent
for a GitHub Pull Request, whose findings are already anchored to a
specific commit/diff location by GitHub itself — `github-pr-review` is
not required to add one, and must not force repository-state categories
onto PR findings that don't have them. A Skill that has no such concept
simply renders the `Location` line without a trailing annotation.

The `_(evidence location; fix/action location unresolved)_` marker from
"Fix/action location, evidence location, publication" is a second
permitted strict trailing addition on this same line. When both apply,
render the source-state annotation first, then the unresolved marker;
neither replaces, reorders, or hides the `` `<path>:<line-or-range>` ``
value.

## Canonical inline rendering

Used for a GitHub inline review comment, where the platform supplies the
file/line anchor and the comment's own identity. `id` and `Location` are
omitted for that reason; severity stays first; fields stay concise:

```text
[<severity>] <short, concrete title>

Evidence: <concrete evidence — what the code actually does>

Impact: <concrete engineering consequence — why it matters>

Fix: <concrete correction direction, when useful>
```

A justified longer explanation adds a single `Details:` line after `Fix:`, on
the same visibility terms as the full rendering.

The inline anchor is the finding's canonical fix/action location, not the
evidence location and not a line chosen because the platform allows a
comment there (see "Fix/action location, evidence location, publication",
and each Skill's placement policy). When the evidence was observed
elsewhere, name that evidence/source location inside the `Evidence:`
prose — there is no separate `Evidence location:` line on this surface.

For a **consolidated root-cause finding**, name the affected call paths
inside the prose — the `Evidence:` block, or a short `Affected call paths:`
list after `Fix:` — so no manifestation site is dropped on this surface.
The anchor stays the shared cause (see "Affected locations on a
consolidated finding").

## Canonical human inline rendering

An **opt-in** projection of the same fields onto a GitHub inline comment,
selected by `human_inline_findings` (see
[`../policies/invocation-options.md`](../policies/invocation-options.md),
"`human_inline_findings` derived default and phrasings" — its default is
derived from `human_review_output`). Used only by `github-pr-review`, and
only for the inline surface: `local-code-review` has no inline comments,
and the full / summary-pointer renderings above are never affected.

It reads the way a strong senior engineer would leave the comment by
hand — a short heading that keeps the severity and names the concrete
finding, then compact prose:

```text
<severity>: <short, concrete finding — what is actually wrong>

<one to three short paragraphs that carry the concrete problem and the
evidence for it, the engineering consequence when it is material or
non-obvious, and an actionable correction direction when one is useful.
A genuine open question or trade-off is phrased as a question, not
asserted as a defect.>
```

Example:

```text
P2: Retry eligibility logic is duplicated

The same eligibility decision is implemented in both the sync and async
flows, so the behaviour can drift when one path changes and the other is
missed. I'd centralise it behind one policy/helper and have both flows
call that.
```

Rules — this is a re-voicing, not a weaker finding:

- **severity stays visible first**, in the heading, as `P0` / `P1` /
  `P2` (here `P2: …`, never `[P2] …`);
- the **mandatory core still holds** — What / Where / Evidence / Impact /
  Fix per "Finding quality contract". "Where" is the inline anchor the
  surface supplies (the canonical fix/action location, unchanged); the
  other four are carried by the prose instead of by labelled fields, and
  none may be dropped, softened to a vague gesture, or replaced by
  generic "consider improving this" language;
- **concise by default** per "Conciseness contract"; two paragraphs is
  not required and the length adapts to the finding;
- **evidence-based** per [`../policies/evidence.md`](../policies/evidence.md);
  genuine **uncertainty is preserved** as a question rather than asserted;
  **no praise** on an inline comment;
- a justified longer explanation ("When a longer explanation is
  justified") is folded into the prose as one extra short paragraph on
  the same visibility terms as `Details` elsewhere — never re-introduced
  as a `Details:` label;
- the finding's **identity, severity, deduplication, canonical
  fix/action location, evidence/detection location, and publication
  anchor are exactly those of the structured inline rendering above** —
  structured and human inline are two renderings of one semantic
  finding, and the choice of rendering never moves the comment off the
  canonical fix/action location or into the review body (that is decided
  only by each Skill's placement policy, independent of voice);
- a **consolidated root-cause finding** still names every affected call
  path in the prose — the re-voicing never drops a manifestation site.

## Canonical summary-pointer rendering

Used when the finding's full representation is published elsewhere (for
example, a GitHub inline comment) and the review body only needs to
reference it — never both in full. The `` `<path>:<line-or-range>` `` is
the canonical fix/action location (or the best-known coordinate with the
unresolved annotation when the fix/action location is unresolved):

```markdown
- **<severity> — <short title>**
  `<path>:<line-or-range>`
```

For a **consolidated root-cause finding** the pointer adds a one-line
affected-locations count or list so the reader still sees the finding
reaches several sites:

```markdown
- **<severity> — <short title>**
  `<shared-cause path>:<line-or-range>` — affects `<path:line>`, `<path:line>`, …
```

## Rules

- one severity per finding, always visible first;
- the mandatory core (`What? Where? Evidence? Impact? Fix?`) is always
  present per "Finding quality contract"; concision never removes any of
  it;
- fields are concise by default per "Conciseness contract"; a longer
  `Details` field is allowed only for a finding in one of the categories
  in "When a longer explanation is justified" and rendered only per the
  detail-precedence rule in `invocation-options.md`;
- the opt-in **human inline rendering** (`human_inline_findings`,
  `github-pr-review` inline surface only) re-voices an inline finding as
  senior-engineer prose without `Evidence:` / `Impact:` / `Fix:` labels;
  it keeps the severity in the heading, the full mandatory core, the
  evidence bar, and the finding's identity, severity, deduplication, and
  canonical location — a projection, never a weaker finding (see
  "Canonical human inline rendering");
- optional fields render only when populated — never as an empty or
  placeholder line (see "Optional and surface-specific fields");
- a **consolidated root-cause finding** additionally carries an **affected
  locations** list naming every manifestation site the shared cause
  reaches; it is rendered on every surface and never replaces `location`
  (see "Affected locations on a consolidated finding");
- evidence-based — no generic "this could be improved" without a
  concrete basis;
- impact is explicit and distinct from the title — it explains
  consequence, not just restates the defect;
- no duplicate findings for the same underlying issue;
- a finding has exactly one authoritative full representation. If it is
  published in full at one location (e.g. inline), every other location
  uses the summary-pointer form instead of repeating the full finding;
- `location` is the canonical fix/action location and is never derived
  from where a platform allows a comment; an `evidence location` renders
  only when it differs from `location` and adds information (see
  "Fix/action location, evidence location, publication");
- an evidence location is never relabeled as a resolved fix/action
  location — an unresolved fix/action location is stated explicitly with
  the trailing annotation;
- `fix` is a direction, never an implemented patch.
