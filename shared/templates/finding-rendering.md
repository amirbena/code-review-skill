# Shared Template — Finding Renderings

The canonical rendering exemplars for a single finding, projected onto each
delivery surface. The **fields and the quality/conciseness contract** these
render are owned by [`finding.md`](finding.md); this file is one projection
of those fields and never changes the finding's identity, severity, evidence
bar, canonical location, or the decision derivation. Read
[`finding.md`](finding.md) first — it is the contract; this file is how that
contract is drawn.

The opt-in senior/human projections — the Senior voice contract, the human
inline rendering, and the human full rendering — live in
[`finding-rendering-human.md`](finding-rendering-human.md), which is loaded
only when `human_review_output` or `human_inline_findings` is in effect. This
file is always loaded and keeps the structured renderings and the rules.

Every `[<severity>]` slot below renders the bare `P0` / `P1` / `P2` code by
default. A Skill that defines the optional severity-legend override in
[`finding.md`](finding.md), "Fields" (`github-pr-review` does, in its own
`policies/review-output.md`) substitutes `[<severity> (<compact
meaning>)]` — e.g. `[P1 (Blocking)]` — everywhere a severity is shown
(full rendering, inline rendering, human inline heading, and
summary-pointer), consistently, with no other change to these shapes,
**only when that Skill's own gating invocation option resolves `true`**
(`github-pr-review`'s is `include_severity_description`, default
`false` — see
[`../policies/invocation-options.md`](../policies/invocation-options.md));
`github-pr-review`'s own default rendering keeps the bare-code form too,
identical in shape to a Skill that declares no legend at all. This is
additive and inert for a Skill that declares no legend
(`local-code-review` does not, and its renderings below stay exactly the
bare-code form regardless of any option's value). Wherever the
parenthetical is shown, it renders inside the same emphasized unit as
the severity and title it accompanies — never as a trailing, separately
emphasized, or unemphasized addition (see each Skill's own
`policies/review-output.md` for the surface-by-surface contract).

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

When [`../policies/remediation-scope-boundary.md`](../policies/remediation-scope-boundary.md)
identifies a broader, legitimately separate concern alongside a bounded
required `Fix`, one `Follow-up` line is added after `Fix` (omitted when no
such concern was identified, or when the broader work is itself the
required `Fix`):

```markdown
### <id> [<severity>] <short, concrete title>

- **Location:** `<path>:<line-or-range>`
- **Evidence:** <concrete evidence, concise>
- **Impact:** <concrete engineering consequence, concise>
- **Fix:** <the smallest correction that restores the current contract>
- **Follow-up:** <the broader, separately-scoped concern, not required in
  this change>
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

When a narrow, well-defined defect class applies to the finding, one
`Defect kind` line is added after `Evidence` (and before any `Contextual
evidence` / `Runtime validation` / `Confidence` / `Capability` lines) —
see [`finding.md`](finding.md), "Defect classification". It is a
classification, not provenance, and never carries a severity:

```markdown
### <id> [<severity>] <short, concrete title>

- **Location:** `<path>:<line-or-range>`
- **Evidence:** <concrete evidence, concise>
- **Defect kind:** `<kebab-case defect-class slug>`
- **Impact:** <concrete engineering consequence, concise>
- **Fix:** <concrete correction direction, not a patch>
```

When contextual evidence informed the finding and materially explains why
the behavior is incorrect or risky, one `Contextual evidence` line is added
after `Evidence` (see [`finding.md`](finding.md), "Contextual evidence and
provenance"). It is a provenance record and never carries a severity;
absent on a finding that rests on code evidence alone:

```markdown
### <id> [<severity>] <short, concrete title>

- **Location:** `<path>:<line-or-range>`
- **Evidence:** <concrete evidence, concise>
- **Contextual evidence:** <the requirement / acceptance criterion /
  accepted decision / repository policy / feedback / historical note that
  informed this finding — source and the specific clause>
- **Impact:** <concrete engineering consequence, concise>
- **Fix:** <concrete correction direction, not a patch>
```

When a targeted runtime check produced a `runtime-confirmed` or
`attempted-inconclusive` state, one `Runtime validation` line is added after
`Evidence` (see [`finding.md`](finding.md), "Runtime validation state and
provenance"). The `reasoned` default is never rendered. It is a provenance
record and never carries a severity:

```markdown
### <id> [<severity>] <short, concrete title>

- **Location:** `<path>:<line-or-range>`
- **Evidence:** <concrete evidence, concise>
- **Runtime validation:** runtime-confirmed — <bounded reproduction and its
  pass/fail evidence> _(or)_ attempted-inconclusive — <what was attempted and
  why it did not confirm>
- **Impact:** <concrete engineering consequence, concise>
- **Fix:** <concrete correction direction, not a patch>
```

When the finding's `confidence` value is anything other than the `credible`
default **and it is not merely the roll-up of a `Runtime validation` line
already shown** (a `runtime-confirmed` line with `confidence` `confirmed`, or
an `attempted-inconclusive` line with `confidence`
`runtime-validation-unavailable`), one `Confidence` line is added after
`Evidence` (and after any `Runtime validation` line) — see
[`finding.md`](finding.md), "Confidence and evidence state". The `credible`
default is never rendered, and neither is a value a shown `Runtime
validation` line already conveys. It never lowers the evidence bar and never
carries a severity:

```markdown
### <id> [<severity>] <short, concrete title>

- **Location:** `<path>:<line-or-range>`
- **Evidence:** <concrete evidence, concise>
- **Confidence:** confirmed _(or)_ runtime-validation-unavailable _(or)_
  external-contract-unvalidated _(or)_ insufficient-context — <one clause on
  the unresolved basis, when the value is not `confirmed`>
- **Impact:** <concrete engineering consequence, concise>
- **Fix:** <concrete correction direction, not a patch>
```

When a domain-specific deepening capability's reasoning contributed the
finding, one `Capability` line is added after `Evidence` (and after any
`Contextual evidence` / `Runtime validation` / `Confidence` lines) — see
[`finding.md`](finding.md), "Capability provenance". It is a provenance
record and never carries a severity; absent on a finding base reasoning
alone already fully supports:

```markdown
### <id> [<severity>] <short, concrete title>

- **Location:** `<path>:<line-or-range>`
- **Evidence:** <concrete evidence, concise>
- **Capability:** security-deepening — <one clause on what the deeper
  investigation established beyond base reasoning>
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

A repository qualifier is a distinct, **leading** addition, not a
trailing one: for `local-code-review`'s explicit, user-authorized
multi-repository Review Target (see that Skill's own
`policies/multi-repository-review-target.md`, not linked from here for
the same standalone-packaging reason as above), the `` `<path>` `` value
itself carries a leading `<repo-alias>:` qualifier —
`` `<repo-alias>:<path>:<line-or-range>` `` — so a reader can tell which
member repository a location belongs to at a glance. It combines with
the trailing annotations above without conflict:

```markdown
- **Location:** `<repo-alias>:<path>:<line-or-range>` _(<annotation>)_
```

A single-repository review (no multi-repository input supplied) never
renders this qualifier — `location` stays exactly `` `<path>:<line-or-range>` ``,
unchanged from before this convention existed.

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

When [`../policies/remediation-scope-boundary.md`](../policies/remediation-scope-boundary.md)
identifies a broader, separately-scoped concern, name it as a distinct
closing sentence inside the `Fix:` prose (e.g. "Separately, ... is a valid
follow-up, not required here") — there is no separate `Follow-up:` line on
this surface. It must stay clearly distinguishable from the required
correction, never phrased as if it were also required now.

The inline anchor is the finding's canonical fix/action location, not the
evidence location and not a line chosen because the platform allows a
comment there (see "Fix/action location, evidence location, publication",
and each Skill's placement policy). When the evidence was observed
elsewhere, name that evidence/source location inside the `Evidence:`
prose — there is no separate `Evidence location:` line on this surface.

When a narrow, well-defined defect class applies to the finding, name it
inside the `Evidence:` prose as well — there is no separate `Defect kind:`
line on this surface (see [`finding.md`](finding.md), "Defect
classification").

When contextual evidence informed the finding, name it inside the
`Evidence:` prose as well — there is no separate `Contextual evidence:`
line on this surface (see [`finding.md`](finding.md), "Contextual evidence
and provenance").

When a targeted runtime check produced a `runtime-confirmed` or
`attempted-inconclusive` state, state it inside the `Evidence:` prose too —
there is no separate `Runtime validation:` line on this surface (see
[`finding.md`](finding.md), "Runtime validation state and provenance"). The
`reasoned` default is not mentioned.

When the finding's `confidence` value is not the `credible` default, state it
inside the `Evidence:` prose as well — there is no separate `Confidence:`
line on this surface (see [`finding.md`](finding.md), "Confidence and
evidence state"). The `credible` default is not mentioned, nor is a value the
prose already conveys through an equivalent `runtime-confirmed` /
`attempted-inconclusive` mention.

When a domain-specific deepening capability contributed the finding, name it
inside the `Evidence:` prose as well — there is no separate `Capability:`
line on this surface (see [`finding.md`](finding.md), "Capability
provenance"). Omitted whenever no capability contributed.

For a **consolidated root-cause finding**, name the affected call paths
inside the prose — the `Evidence:` block, or a short `Affected call paths:`
list after `Fix:` — so no manifestation site is dropped on this surface.
The anchor stays the shared cause (see "Affected locations on a
consolidated finding").

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

These are the rendering-specific rules; the finding-field and
quality-contract rules are in [`finding.md`](finding.md), "Rules".

- the opt-in **human inline rendering** (`human_inline_findings`,
  `github-pr-review` inline surface only) re-voices an inline finding as
  senior-engineer prose without `Evidence:` / `Impact:` / `Fix:` labels;
  it keeps the severity in the heading, the full mandatory core, the
  evidence bar, and the finding's identity, severity, deduplication, and
  canonical location — a projection, never a weaker finding (see
  [`finding-rendering-human.md`](finding-rendering-human.md), "Canonical
  human inline rendering");
- the opt-in **human full rendering** (`human_review_output`,
  `github-pr-review` body/fallback surface only) applies the same
  re-voicing to a finding rendered in full in the review body, keeping
  `id` and `Location` as their own line since the body has no
  platform-supplied anchor; it is selected directly by
  `human_review_output`, not by `human_inline_findings`, and is likewise
  a projection, never a weaker finding (see
  [`finding-rendering-human.md`](finding-rendering-human.md), "Canonical
  human full rendering");
- optional fields render only when populated — never as an empty or
  placeholder line (see [`finding.md`](finding.md), "Optional and
  surface-specific fields");
- the **Confidence** line renders on the full rendering only when the value
  is not the `credible` default and is not already conveyed by a shown
  `Runtime validation` line; on the inline surface it folds into the
  `Evidence:` prose, never as its own line; it never lowers the evidence bar
  and never carries a severity (see [`finding.md`](finding.md), "Confidence
  and evidence state");
- the **Capability** line renders on the full rendering only when a
  domain-specific deepening capability contributed the finding; on the
  inline surface it folds into the `Evidence:` prose, never as its own
  line; it never carries a severity and never changes identity,
  deduplication, or the decision derivation (see [`finding.md`](finding.md),
  "Capability provenance");
- the **Defect kind** line renders on the full rendering only when a
  narrow, well-defined defect class applies to the finding; on the
  inline surface it folds into the `Evidence:` prose, never as its own
  line; it is a classification, never a severity input, and never
  changes identity, deduplication, or the decision derivation (see
  [`finding.md`](finding.md), "Defect classification");
- a finding has exactly one authoritative full representation. If it is
  published in full at one location (e.g. inline), every other location
  uses the summary-pointer form instead of repeating the full finding.
