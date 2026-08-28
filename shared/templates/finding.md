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
predictable enough for a coding agent to parse and act on. A future
additional renderer (for example a machine-readable one) would be another
projection of the same fields; it would not change the finding fields,
the severity model, the evidence bar, or the decision derivation. Do not
make the human-facing review a machine-only format.

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
- **location** — the most precise useful location available: file,
  changed line/range, symbol/function, or narrow section. Prefer
  precision; never invent a location that doesn't exist;
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

- **details** — the longer explanation permitted by "When a longer
  explanation is justified" above. Present only for a finding in one of
  those categories; absent otherwise;
- **source annotation on `location`** — a Skill may append a short
  parenthetical after the location value when it has its own concept that
  classifies *where the finding's evidence came from* within that Skill's
  source-state model (see "Location source annotation" below). Present
  only for a Skill that has such a concept;
- **implementation prompt** — `local-code-review` only, and only under its
  explicit `include_fix_prompt` opt-in, appended after `Fix` for a
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
always in the same order, so an agent can rely on it.

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

A finding that meets "When a longer explanation is justified" adds one
`Details` field, immediately after `Evidence`:

```markdown
### <id> [<severity>] <short, concrete title>

- **Location:** `<path>:<line-or-range>`
- **Evidence:** <concrete evidence, concise>
- **Details:** <the cross-file / concurrency / security / invariant
  explanation the evidence needs to be understood — a short paragraph,
  not an essay>
- **Impact:** <concrete engineering consequence, concise>
- **Fix:** <concrete correction direction, not a patch>
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

A justified longer explanation adds a single `Details:` line between
`Evidence:` and `Impact:`, on the same terms as the full rendering.

## Canonical summary-pointer rendering

Used when the finding's full representation is published elsewhere (for
example, a GitHub inline comment) and the review body only needs to
reference it — never both in full:

```markdown
- **<severity> — <short title>**
  `<path>:<line-or-range>`
```

## Rules

- one severity per finding, always visible first;
- the mandatory core (`What? Where? Evidence? Impact? Fix?`) is always
  present per "Finding quality contract"; concision never removes any of
  it;
- fields are concise by default per "Conciseness contract"; a longer
  `Details` field is allowed only for a finding in one of the categories
  in "When a longer explanation is justified";
- optional fields render only when populated — never as an empty or
  placeholder line (see "Optional and surface-specific fields");
- evidence-based — no generic "this could be improved" without a
  concrete basis;
- impact is explicit and distinct from the title — it explains
  consequence, not just restates the defect;
- no duplicate findings for the same underlying issue;
- a finding has exactly one authoritative full representation. If it is
  published in full at one location (e.g. inline), every other location
  uses the summary-pointer form instead of repeating the full finding;
- `fix` is a direction, never an implemented patch.
