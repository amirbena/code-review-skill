# Stable Finding Identity — Derivation Contract

Repository-development contract for GitHub Issue
[#60](https://github.com/amirbena/code-review-skill/issues/60). It defines the
**one canonical, deterministic construction** for a finding's stable identity
and for the normalized descriptor primitives the matching strategy consumes.

It sits directly under two already-settled sources and does not reopen either:

- the identity **requirements** in
  [`finding-identity-requirements.md`](finding-identity-requirements.md)
  ([#58](https://github.com/amirbena/code-review-skill/issues/58)) — what must
  survive, what must change, determinism, portability, fail-toward-splitting;
- the identity **matching strategy** in
  [`finding-matching-strategy.md`](finding-matching-strategy.md)
  ([#59](https://github.com/amirbena/code-review-skill/issues/59)) — the
  precision-first staged hybrid, its two proof axes, its
  `MATCH` / `AMBIGUOUS` / `NO MATCH` outcomes, and the
  [#59 → #60 ownership boundary](finding-matching-strategy.md) that assigns
  **canonical construction of the descriptor primitives to this document**.

This is a repository-development doc, like
[`finding-identity-requirements.md`](finding-identity-requirements.md) and
[`runtime-parallelism.md`](runtime-parallelism.md): it is **not** packaged into
either Skill archive, and no packaged Skill resource depends on it. Its
standing relative to the eventual packaged runtime policy is in "Status and
canonical home" at the end.

The finding fields this document is expressed over are the shared finding
contract in [`../shared/templates/finding.md`](../shared/templates/finding.md).

---

## Summary

Each point is stated normatively in the section named; this list only orients.

- **Two layers, one direction** (§1). A **canonical finding descriptor** is
  built from the reviewed evidence; a **minted stable identity** is a digest
  over the discriminating subset of that descriptor. Nothing flows the other
  way.
- **One documented derivation per primitive** (§3). `location_intent`, `path`,
  `symbol`, `construct`, `anchor_tokens`, `context_tokens` (occurrence
  context), `neighboring_syntax`, `behavioral_claim`, `cause_key`,
  `behavior_key`, `mechanism_key`, and `defect_kind` each have exactly one
  construction rule here.
- **Absent and unclassifiable are explicit and distinct** (§4). `ABSENT` (the
  input does not carry this facet) and `UNCLASSIFIABLE` (present but not
  conservatively reducible) are two sentinels. Neither ever compares equal to
  anything — including another sentinel — and neither is a wildcard.
- **Deterministic and offline** (§5). The descriptor and the minted identity
  are a pure function of the finding fields and the reviewed source at the
  compared revision. No wall clock, RNG, environment, worker/shard index,
  discovery order, severity, display ordinal, HEAD SHA, PR number, or
  repository-state annotation is an input.
- **Portable across both Skills** (§5). Only inputs both Skills possess feed
  the descriptor. An optional parser may refine diagnostic fields but never
  changes a hashed value, so the minted identity is identical under
  `local-code-review` and `github-pr-review` for the same finding on the same
  state.
- **Identity is not matching and not lifecycle** (§6). #60 mints a fresh
  identity and defines the single hand-off point where a prior identity is
  propagated. **Which** prior finding (if any) a current finding continues is
  #59's decision; what state the identity is in is
  [#62](https://github.com/amirbena/code-review-skill/issues/62)'s.
- **Fail closed** (§7). A finding whose discrimination reduces to
  repository / path / `anchor_tokens` — no classified `symbol`,
  `mechanism_key`, `cause_key`, or `behavior_key` — or whose repository or
  location intent is unresolvable, is still minted deterministically but is
  emitted **not eligible for automatic matching**. Prefer a false split.

---

## 1. Two layers

```text
finding fields + reviewed source at the compared revision
        │
        ▼
canonical finding descriptor        (§3 primitives, §4 sentinels)
        │  discriminating subset only (§6)
        ▼
canonical serialization  →  SHA-256  →  minted stable identity  (fid_v1_…)
        │
        ▼
effective identity = propagated prior identity on #59 MATCH,
                     otherwise the minted identity            (§6)
```

- The **descriptor** is matching evidence and diagnostics. #59 reads it.
- The **minted identity** is the identity a finding gets when nothing prior is
  known to continue. It is content-addressed over the descriptor's
  discriminating subset, so equivalent review inputs always mint the same
  value.
- The **effective identity** is what a finding carries out of a review: the
  minted identity on a first review or a #59 `NO MATCH` / `AMBIGUOUS`; the
  established prior identity on a #59 `MATCH`.

This document defines the descriptor, the minting function, and the hand-off
rule. It does not define matching, lifecycle state, review-delta computation,
state persistence, or a rendered output schema.

## 2. Inputs

Per [`finding-identity-requirements.md`](finding-identity-requirements.md) §4
and [`finding-matching-strategy.md`](finding-matching-strategy.md) §1, both
Skills can supply: repository identity; normalized repository-relative path (or
an explicit no-single-file intent); the finding `title`, `evidence`, `impact`,
`fix`; the changed set; and the current file content at the compared revision.
Line/range, enclosing symbol, construct kind, surrounding source context,
rename/refactor mappings, and prior findings are **conditional** — present for
some findings only.

A conditional input that is absent produces `ABSENT` (§4). It never produces a
guessed value and never widens equivalence.

The construction must not require a language server, a per-language parser, a
semantic index, a network service, runtime observation, Git history beyond the
two compared states, or generated prose to stay word-for-word stable.

## 3. Descriptor primitives — canonical construction

Every primitive below is built by the rule stated. "Normalized token list"
means the output of the tokenizer in §3.1, in source order.

### 3.1 Token normalization

The single tokenizer used by `anchor_tokens`, `context_tokens`,
`neighboring_syntax`, `cause_key`, `behavior_key`, and `mechanism_key`:

1. **Outside string literals**, delete block comments (`/* … */`) and
   `#`-to-end-of-line comments. Quoted string literals are copied verbatim,
   so a URL, a `//` path, or a `#fragment` inside quotes is preserved. `//`
   is **not** treated as a comment: it is ambiguous with floor division
   (`a // b`) and other operator runs, so it is tokenized as an operator; an
   anchor fragment — the smallest fragment that demonstrates the defect —
   rarely carries trailing line commentary. An unterminated quote in a
   fragment consumes the rest of it (conservative, still deterministic).
2. Delete ASCII control characters (`U+0000`–`U+001F`, `U+007F`).
3. Collapse every whitespace run to a single space.
4. Emit tokens in order, each being one of: an identifier/keyword
   (`[A-Za-z_][A-Za-z0-9_]*`); a numeric literal (`\d+(?:\.\d+)?`); a quoted
   string literal, kept verbatim including its quotes; a maximal run of
   operator characters (`- + * / % = ! < > & | ^ ~ .`); or a single bracket
   (`(` `)` `[` `]` `{` `}`).
5. Do **not** emit `,` or `;` — trailing commas and statement terminators vary
   with formatting.
6. Preserve order and multiplicity. Case is preserved (identifiers and
   negation carry meaning).

This normalization is stable across the must-survive formatting scenarios in
[`finding-identity-requirements.md`](finding-identity-requirements.md) §2
(whitespace, indentation, line wrapping, brace style, trailing commas, comment
reflow, line-number movement) and does not merge the must-change scenarios in
§3 (a changed operator, literal, identifier, or negation changes the tokens).

### 3.2 Primitive rules

| Primitive | Construction | Absent / unclassifiable |
|---|---|---|
| `location_intent` | Closed enum `line \| symbol \| file \| cross_file \| repository`, from the finding's `location` precision. | A `location` that matches none of the five → `UNCLASSIFIABLE`. |
| `path` | Repository-relative, `\`→`/`, leading `./` removed, any leading `/` or `drive:/` prefix removed, `.`/`..` segments rejected. Repository case rules (case-sensitive unless the repository is known case-insensitive). | `location_intent ∈ {cross_file, repository}` → `ABSENT`. No usable path where one is expected → `ABSENT`. |
| `symbol` | The enclosing **qualified** symbol as determined by a lightweight, language-neutral lexical scan of the reviewed source (nearest enclosing named definition chain, joined with `.`), trimmed, internal whitespace collapsed. | Lexical scan cannot name it → `ABSENT`. Never guessed. A parser may fill `diagnostic_symbol` (§5) but not this field. |
| `construct` | Closed enum `statement \| declaration \| call \| expression \| config_key \| section \| block`, chosen by the same conservative lexical scan. | None fits → `UNCLASSIFIABLE`. |
| `anchor_tokens` | §3.1 over the **smallest source or config fragment that demonstrates the defect** (the reviewer-provided evidence fragment at the reviewed revision). | Empty fragment → empty list (a finding with no source-backed anchor is handled by §7). |
| `context_tokens` | §3.1 over the source of the sibling statements inside the enclosing `symbol`/`section`, with the longest contiguous run equal to `anchor_tokens` removed, then truncated to the first `CONTEXT_TOKEN_CAP` tokens. `CONTEXT_TOKEN_CAP = 64`. This is the **occurrence context**. | No enclosing sibling source available → `ABSENT`. |
| `neighboring_syntax` | An ordered pair `(predecessor, successor)`: §3.1 over the nearest stable statement immediately before, and immediately after, the anchor within its `symbol`/`section`, each independently. | A side with no stable neighbor → that side is `ABSENT`. |
| `behavioral_claim` | The finding's concise cause → faulty-behavior statement (excluding impact, fix, severity), case-folded, whitespace-collapsed, trimmed. Identifiers, negation, numbers, and operators are **kept**. | Empty → `ABSENT`. |
| `cause_key` | §3.1 over the substring of `behavioral_claim` **before** the first cause→behavior connective in `{" so ", " causing ", " resulting in ", " leads to ", " which causes ", " therefore ", " -> ", " → "}`, after trimming **trailing** whitespace and sentence punctuation (`. , ; : ! ?`) and **leading whitespace only** from the clause. A leading `!` is negation and is preserved (matching-strategy.md §2). | No connective, or empty left side → `UNCLASSIFIABLE`. |
| `behavior_key` | §3.1 over the substring of `behavioral_claim` **after** that first connective, trimmed the same way. | No connective, or empty right side → `UNCLASSIFIABLE`. |
| `mechanism_key` | §3.1 over the **reviewer-provided source fragment naming the unsafe operation or violated invariant** at the reviewed revision. #60 only normalizes this fragment; it does not extract it heuristically. | No fragment provided → `UNCLASSIFIABLE`. |
| `defect_kind` | The narrow defect class: the controlled-vocabulary slug when one applies, otherwise a conservative slug of the reviewer phrase (case-folded, non-`[a-z0-9]` runs → single `_`, trimmed of `_`). Built for #59; **not** in the minted digest (§6.1) — a free-form phrase slug is not a stable hash discriminator. | Empty → `UNCLASSIFIABLE`. |

Constants (`CONTEXT_TOKEN_CAP`, the connective set, the enum members, the
identity scheme tag in §6) are fixed by this contract and changed only by
revising it, with the [#61](https://github.com/amirbena/code-review-skill/issues/61)
regression suite updated in the same change.

## 4. Absent vs. unclassifiable

Two sentinels, never interchangeable:

- **`ABSENT`** — the finding legitimately does not carry this facet (a
  repository-scoped finding has no `path`; a finding with no surrounding
  source has no `context_tokens`).
- **`UNCLASSIFIABLE`** — the facet is present in the inputs but cannot be
  reduced to a canonical value **conservatively**, i.e. without guessing.

Rules:

1. Neither sentinel compares equal to any real value.
2. Neither sentinel compares equal to the other, or to another instance of
   itself, for **matching** purposes — a missing facet never satisfies an
   equality predicate in [`finding-matching-strategy.md`](finding-matching-strategy.md)
   §2.
3. For **minting** (§6) the two sentinels serialize to two fixed, distinct
   byte markers so the digest stays a total function. This does not make a
   sentinel a wildcard: a sentinel in a discriminating field can only
   *reduce* discrimination, never broaden equivalence, and when sentinels
   leave a descriptor with no classified strong semantic field (`symbol`,
   `mechanism_key`, `cause_key`, `behavior_key`) §7 makes the finding
   non-matchable.
4. A sentinel is never replaced by a default, a nearby value, or a
   parser guess to "improve" recall.

## 5. Determinism, offline reproducibility, portability

The descriptor and the minted identity are a pure function of:

- the finding's `location`, `title`, `evidence`, `impact`, `fix`, and its
  concise behavioral claim / mechanism / defect-kind inputs; and
- the reviewed source at the compared revision (fragments and enclosing
  context).

They **must not** read: wall-clock time, random seeds, environment variables,
the machine, the number of review workers or shards, finding discovery or
emission order, the count of other findings, `severity`, the `F1`/`F2` display
ordinal, the HEAD SHA, the PR number, or the `local-code-review`
repository-state annotation. Any of these passed alongside the inputs is
ignored.

**Portability.** Only inputs both Skills possess feed the descriptor's hashed
subset (§6). Where a runtime has a parser, it may populate a separate
`diagnostic_symbol` / `diagnostic_construct` for #59 candidate generation and
for human diagnostics, but those are **not** hashed and **not** equality
inputs for a supported edge. Consequently the minted identity for one finding
on one reviewed state is identical whether it was produced by
`local-code-review` or by `github-pr-review`, with or without a parser
available.

## 6. Minting and the identity hand-off

### 6.1 Discriminating subset

The minted identity is a digest over exactly these descriptor fields, in this
order:

```text
repository, location_intent, path, symbol, construct,
anchor_tokens, mechanism_key, cause_key, behavior_key
```

`cause_key` and `behavior_key` **are** in the digest. They are the semantic
distinction between two defects that share a site and a code snippet — a SQL
-injection finding and a cross-tenant-leak finding on the same
`db.execute(q)` line differ only there. Excluding them would let those two
mint one identity, a silent **false merge**, which
[`finding-identity-requirements.md`](finding-identity-requirements.md) §6
calls a safety failure. The cost is the opposite direction: a behavioral
claim reworded enough to change its *normalized* `cause_key` / `behavior_key`
tokens re-mints the identity — a visible **false split**, the recoverable
direction (§6). A definite #59 `MATCH` (anchor-backed defect proof plus an
independent site proof) then re-propagates the prior identity — the same
mechanism already relied on when a defect's enclosing `symbol` changes.
Trivial phrasing changes — case, surrounding whitespace, trailing sentence
punctuation, dropped commas — do not change the normalized `cause_key` /
`behavior_key` tokens and keep the identity.

Three groups of primitives are **deliberately excluded** from the digest:

- `context_tokens` and `neighboring_syntax` — occurrence context. They exist
  to help #59 decide *which* occurrence continued, and they change under the
  exact formatting / line-movement / nearby-edit scenarios that
  [`finding-identity-requirements.md`](finding-identity-requirements.md) §2
  requires the identity to survive.
- `behavioral_claim` — the raw reviewer prose. Only its normalized
  extractions (`cause_key` / `behavior_key`) discriminate; the prose itself
  is not hashed.
- `defect_kind` — a conservative slug of a free-form reviewer phrase
  (`missing null check` vs `no null-check` slug differently). Free-form
  wording is not a stable hash discriminator, so `defect_kind` is not hashed.
  It is still built and still consumed by #59 as controlled-vocabulary-or
  -phrase evidence.

Excluding a primitive from the digest never lets it act as a wildcard: it is
still built, still recorded, and still used by #59. Conversely, adding a
field to the digest can only *narrow* what mints the same identity — it never
broadens #59's equivalence or changes its supported / ambiguity / no-edge
outcomes.

### 6.2 Canonical serialization

Each field is encoded unambiguously and length-delimited:

- a string `s` → `len(s) "\x1f" s` (length-prefixed);
- a token list `t` → `len(t) "\x1f" join("\x1f", t)` (count-prefixed; §3.1
  already removed control characters, including `\x1f`, from every token);
- `ABSENT` → the fixed marker `\x00A`; `UNCLASSIFIABLE` → `\x00U`.

Fields are joined in the §6.1 order with `\x1e`, each behind its fixed
`<name>\x1d` marker, and the whole is prefixed with the identity scheme tag
`v1` and `\x1e`. Collision-freedom comes from this framing — the fixed field
names, the fixed field order, and the length/count prefix on every value —
**not** from control characters being absent from every field: `repository`,
`path`, and `symbol` are hashed as-is and may contain any character. Because
each value's byte length is known from its prefix and its position is pinned
by the preceding `<name>\x1d`, a separator appearing inside a value cannot be
mistaken for a structural delimiter, so no two distinct descriptors serialize
to the same string.

### 6.3 Minted identity

```text
minted = "fid_" + "v1" + "_" + hex( SHA-256( canonical_serialization ) )[:32]
```

`fid_` marks the value as a finding identity; `v1` is the scheme version;
the 128-bit hex prefix is the content address. The value is lowercase and
stable for identical inputs on any machine, offline, in either Skill.

### 6.4 Hand-off with #59

#60 owns identity; #59 owns whether a current finding continues a prior one.

- **First review, or #59 `NO MATCH`, or #59 `AMBIGUOUS`** → the current
  finding's effective identity is its **minted** identity. `AMBIGUOUS` never
  inherits — this is [`finding-identity-requirements.md`](finding-identity-requirements.md)
  §7 and [`finding-matching-strategy.md`](finding-matching-strategy.md) Step 6.
- **#59 `MATCH`** → the current finding's effective identity is the
  **established prior identity**, propagated unchanged, **provided the
  current descriptor is itself eligible for automatic matching (§7)**. A
  non-matchable descriptor always takes its freshly minted identity, even if
  a prior identity is offered, so a caller cannot bypass fail-closed at the
  hand-off. The minted value is retained only as diagnostics.

#60 performs no candidate generation, no proof-axis evaluation, and no global
bipartite resolution. It consumes a single already-decided #59 outcome per
current finding. It therefore cannot broaden #59's equivalence or change its
supported / ambiguity / no-edge results: a normalization choice here only
affects whether two descriptors are *byte-identical*, which is strictly
narrower than #59's proof gates and is one of the equality inputs #59 already
assumes.

## 7. Fail-closed conditions

A current finding takes a fresh **minted** identity and is **not eligible for
automatic matching** (its descriptor is still recorded for diagnostics) when
any of the following holds:

- repository identity is missing or unresolvable;
- `location_intent` is `UNCLASSIFIABLE`, or the prior finding's location intent
  is incompatible;
- the finding has **no source-backed discriminator** — `anchor_tokens` is
  empty **and** `mechanism_key` is `UNCLASSIFIABLE`;
- the descriptor's discrimination **reduces to repository / path /
  `anchor_tokens`** (and at most `construct`) — none of `symbol`,
  `mechanism_key`, `cause_key`, or `behavior_key` is classified. Two
  materially distinct findings can share the same file, line, and code
  snippet, so `{repository, path, anchor_tokens}` alone is never enough to
  license an automatic match;
- the reviewed source needed to build `anchor_tokens` or `mechanism_key`
  cannot be read at one of the two compared states.

Such a finding is still minted deterministically (so it has a stable
identifier), but it is emitted as **not eligible for automatic matching** —
two distinct findings that reduce to the same `{repository, path,
anchor_tokens}` therefore never inherit one another's identity.

This is the requirements' asymmetric error budget
([`finding-identity-requirements.md`](finding-identity-requirements.md) §6): a
false split is visible and recoverable; a false merge is silent. When in
doubt, split.

## 8. Scope boundaries

| Not defined here | Owner |
|---|---|
| Which prior finding a current finding matches; proof axes; ambiguity edges; global resolution | [#59](https://github.com/amirbena/code-review-skill/issues/59), [`finding-matching-strategy.md`](finding-matching-strategy.md) |
| Lifecycle states (`OPEN` / `RESOLVED`) and evidence-gated transitions | [#62](https://github.com/amirbena/code-review-skill/issues/62), [`finding-lifecycle-contract.md`](finding-lifecycle-contract.md) |
| Reviewed-SHA state record and its invalidation | [#63](https://github.com/amirbena/code-review-skill/issues/63), [`reviewed-sha-state-contract.md`](reviewed-sha-state-contract.md) |
| Review-delta semantics (fixed / unchanged / moved / reopened / newly introduced) | [#64](https://github.com/amirbena/code-review-skill/issues/64) |
| Loading prior state, applying transitions, emitting per-finding state, full-review fallback | [#65](https://github.com/amirbena/code-review-skill/issues/65) |
| Identity regression fixtures and their assertions | [#61](https://github.com/amirbena/code-review-skill/issues/61) |
| A rendered / machine-readable output schema and its versioning | [#44](https://github.com/amirbena/code-review-skill/issues/44) |
| Human-facing `F1` / `F2` display IDs; same-HEAD publish de-duplication | [`../shared/templates/finding.md`](../shared/templates/finding.md); [`../skills/github-pr-review/policies/pr-scope.md`](../skills/github-pr-review/policies/pr-scope.md) |

The `F1` / `F2` display ordinals are unchanged. The stable identity defined
here is a separate value in the finding model; a first review mints it and
carries it in-model so a later re-review ([#64](https://github.com/amirbena/code-review-skill/issues/64)
/ [#65](https://github.com/amirbena/code-review-skill/issues/65)) can propagate
or re-mint it. This document does not add a rendered field or change any
template.

## 9. Known limitations

The conservative rules here will mint a fresh identity — a visible false split,
never a silent merge — when the reviewed source for an anchor cannot be read at
both states, when a finding has only prose and no source-backed anchor or
mechanism fragment, when a defect moves to a differently named symbol with no
#59 `MATCH`, when `behavioral_claim` has no separable cause→behavior
connective, or when a behavioral claim is reworded enough to change its
normalized `cause_key` / `behavior_key` tokens. A finding that reduces to
repository / path / `anchor_tokens` only is emitted non-matchable rather than
risk merging two distinct defects at one snippet. These are the accepted cost
of the requirements' false-merge asymmetry and are the same limitation class
[`finding-matching-strategy.md`](finding-matching-strategy.md) §8 records.

## Status and canonical home

Until a packaged runtime policy exists, **this document is the canonical
derivation record** for stable finding identity and descriptor-primitive
construction, and
[`finding-identity-requirements.md`](finding-identity-requirements.md) remains
the canonical requirements record it is built against.

When [#65](https://github.com/amirbena/code-review-skill/issues/65) installs
equivalent behavior in a packaged resource (a `shared/policies/` file or an
extension of an existing one), **that policy becomes the single normative
source**; this document then becomes its design record, links to it, and stops
evolving the rule independently.
