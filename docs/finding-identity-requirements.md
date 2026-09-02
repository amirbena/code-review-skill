# Finding Identity — Requirements

Repository-development doc. It defines **what makes two review findings the
"same finding" across separate review runs**, so the follow-on work can be
done against a fixed contract instead of rediscovering the problem:

- research and strategy selection — GitHub Issue
  [#59](https://github.com/amirbena/code-review-skill/issues/59);
- implementation of a stable identifier on each finding — GitHub Issue
  [#60](https://github.com/amirbena/code-review-skill/issues/60);
- identity regression tests — GitHub Issue
  [#61](https://github.com/amirbena/code-review-skill/issues/61);
- parent capability — GitHub Issue
  [#42](https://github.com/amirbena/code-review-skill/issues/42).

This file is **requirements only**. It does **not** choose or design a
matching mechanism. Wherever a requirement below bounds a tolerance or
names candidate techniques — structural hashing, fuzzy location matching,
semantic similarity, a hybrid — **selecting the technique and the exact
value is [#59](https://github.com/amirbena/code-review-skill/issues/59)'s
decision**; this document only sets the bound that selection must satisfy,
so all four approaches stay comparable there.

This is a repository-development doc, like
[`runtime-parallelism.md`](runtime-parallelism.md): it is **not** packaged
into either Skill archive, and no packaged Skill resource depends on it.
Its standing relative to the eventual runtime policy is defined in
"Status and canonical home" at the end.

The finding fields these requirements are expressed over are the shared
finding contract in
[`../shared/templates/finding.md`](../shared/templates/finding.md).

---

## Summary

Each point is stated normatively in the section named; this list only
orients.

- **Identity tracks a defect, not a line and not a sentence** (§1). The
  same underlying problem in the same program element is the same identity;
  similar wording or a shared location is not.
- **Stability is asymmetric** (§2, §3, §5). Identity survives
  movement/reformatting of unchanged defective code; it changes when the
  defect, or its program element, is materially different.
- **Determinism is required** (§5). Same finding + same target state → the
  same identity, every run.
- **Portable across both Skills** (§5). The same defect in the same change
  gets one identity whether `local-code-review` or `github-pr-review`
  produced the finding.
- **Fail toward splitting, never toward merging** (§6). An uncertain match
  is treated as distinct.
- **No resolution behavior is defined here** (§7, §8). Resolve / re-open /
  suppress / carry-forward belongs to the finding lifecycle
  ([#43](https://github.com/amirbena/code-review-skill/issues/43),
  [#62](https://github.com/amirbena/code-review-skill/issues/62)), not to
  this contract.

---

## 1. What finding identity represents

A **finding identity** answers one question across two reviews of the same
evolving change:

> Is *this* finding the same problem the earlier review already reported, or
> a different one?

It is the join key the finding lifecycle and delta/re-review work build on.
It is **not** a lifecycle state, a severity, or a verdict.

### The four distinctions identity must get right

| Situation | Same identity? | Why |
|---|---|---|
| The **same underlying defect** is observed again — same faulty behavior, same root cause, same program element — after unrelated edits elsewhere | **Yes** | Identity follows the defect; incidental change around it does not create a new problem. |
| A second finding has **similar wording / rationale** to an earlier one but describes a **different underlying problem** | **No** | Identity is not text similarity. Two findings can be phrased almost identically and still be unrelated defects. |
| A finding sits at the **same file and line/range** as an earlier one but is a **different defect** (the original was fixed, or a new issue now occupies that location) | **No** | Location is a signal, not the identity. Same address, different problem = different finding. |
| The **same defect's code moved** — shifted by line-number changes, relocated within the file, reindented — while the defect itself is materially unchanged | **Yes** | Physical position is volatile; the defect is what persists. |

### Identity vs. the existing per-review and same-HEAD identifiers

Two related concepts already exist and are **not** what this document
specifies:

- **Human-facing display IDs (`F1`, `F2`, …)** in
  [`../shared/templates/finding.md`](../shared/templates/finding.md) are
  ordinals *within one review's output*, not stable across runs.
- **`github-pr-review`'s same-HEAD deterministic identity** in
  [`../skills/github-pr-review/policies/pr-scope.md`](../skills/github-pr-review/policies/pr-scope.md),
  "Existing review awareness," suppresses the *same workflow re-publishing
  the same finding for the same PR and the same HEAD*. It deliberately
  binds to the HEAD SHA and exact location and is not required to survive
  code movement.

Cross-review finding identity is the **movement-tolerant superset**: it
MUST remain usable when the HEAD SHA changed and code moved, and MUST stay
consistent with the same-HEAD identity (§5.6).

---

## 2. Must-survive scenarios (identity stays the same)

The defective code and the defect are materially unchanged; only the
surroundings or the presentation moved. Identity **MUST** be stable across
all of these:

1. **Line-number movement.** Code above the finding was added or removed, so
   the finding's line/range number shifted, but the finding's own code is
   untouched.
2. **Nearby unrelated edits.** An adjacent function, import block, comment,
   or sibling statement changed; the defective element did not.
3. **Code reformatting.** Whitespace, indentation, line wrapping, brace
   style, trailing commas, or comment reflow changed over the finding's
   code without changing its behavior.
4. **Insertion/removal of surrounding lines.** Lines were inserted or
   deleted immediately before/after the finding (e.g. a new guard clause
   earlier in the same function) without altering the defective statement.
5. **File-local movement of the defect.** The defective block was moved to a
   different position in the same file — reordered within a function, moved
   to another function in the same file, or hoisted/lowered — while
   remaining the same defect in the same logical role.
6. **Reviewer wording changed.** The later review states the same defect
   with a different `title`, `evidence`, or `fix` phrasing. Identity tracks
   the defect, not the sentence.
7. **Severity re-classification of the same defect.** The same underlying
   defect is re-rated (e.g. `P2` → `P1`) because impact was reassessed.
   Identity represents the defect, not its severity label, so a pure
   severity re-rating **MUST NOT** create a new cross-review identity. The
   same-HEAD identity in
   [`../skills/github-pr-review/policies/pr-scope.md`](../skills/github-pr-review/policies/pr-scope.md)
   **may** fold severity into its own value; reconciling that mechanism
   with this one is owned by
   [#59](https://github.com/amirbena/code-review-skill/issues/59). (§5.6
   does not govern this interaction — it only governs the separate
   constraint that cross-review identity must not split findings the
   same-HEAD rule treats as one within a single unchanged state.)
8. **Cross-Skill re-review of the same change.** The change was reviewed
   once by `local-code-review` on the local delta and again by
   `github-pr-review` on the PR built from it (or vice versa). The same
   defect MUST carry the same identity across that hand-off (§5.5).
9. **Re-review after a rebase or history rewrite of the branch** that leaves
   the defective code textually the same, even though commit SHAs and the
   review base changed.

Cross-check against the re-review change classes in
[#43](https://github.com/amirbena/code-review-skill/issues/43) /
[#64](https://github.com/amirbena/code-review-skill/issues/64):
**`unchanged`** and **`moved`** map to *stable identity*; **`reopened`**
(a previously fixed defect that regressed) MUST *reuse the original
identity* so the lifecycle can express a re-open rather than invent a new
problem.

---

## 3. Must-change scenarios (a new identity is required)

Textual or positional similarity **MUST NOT** collapse these into one
identity:

1. **A genuinely different defect.** Different faulty behavior, different
   root cause, or a different invariant violated — even if it is on the same
   line, in the same function, or described with nearly the same words as an
   earlier finding.
2. **A different semantic location / program element.** The *same kind* of
   defect (same pattern, same rationale text) occurring in a different
   function, method, class, symbol, or distinct logical site is a separate
   finding per site — e.g. the same missing-validation pattern in two
   different handlers is two findings, not one.
3. **Old defect fixed, distinct defect appears nearby.** The earlier
   finding's defect was corrected, and a *different* problem now exists at
   or near the same location. The new problem gets a new identity; the old
   identity does not transfer to it (it stays attached to the now-fixed
   finding for the lifecycle layer to mark resolved).
4. **Similar wording, different underlying problem.** Two findings whose
   `title`/`evidence` read alike but which describe unrelated defects (e.g.
   "unhandled error path" in two unrelated modules for two unrelated
   reasons) MUST stay distinct.
5. **Same message text, different file or symbol.** Re-using a finding's
   phrasing at a new path or new element does not carry its identity there.
6. **Scope/intent of the finding changed.** A file-level or cross-cutting
   finding (no single line) and a line-specific finding in the same file are
   different findings even if they touch the same concern, because their
   location intent differs.

`newly introduced` in
[#43](https://github.com/amirbena/code-review-skill/issues/43) always maps
to a *fresh identity*.

Identity **MUST NOT** be derived from normalized message-text similarity
alone, or from file + line alone: the first fails scenarios 1, 2, and 4
above; the second fails scenario 3 above and scenarios 1–5 in §2. Identity
is derived from *the defect in its program element*.

---

## 4. Inputs available at review time

**Availability is not identity-binding.** This section lists the signals an
identity mechanism *may read*. Listing a signal here does **not** permit
the identity value to *depend on* it. Which signals may **determine**
identity, and which may only **inform** it, is governed by §5 — §5.3 for
position, §5.5 for Skill-specific metadata — and by §2.7 for severity. A
signal marked *informing only* below MAY be consulted but MUST NOT be a
component the identity value is bound to.

The finding fields are those in
[`../shared/templates/finding.md`](../shared/templates/finding.md); the
target/context concepts are those in
[`../shared/policies/review-context.md`](../shared/policies/review-context.md)
and
[`../shared/policies/review-evidence.md`](../shared/policies/review-evidence.md).

### 4.1 Guaranteed — always present for any actionable finding

- **Repository-relative file path** of the finding (normalized;
  `/`-separated). For a genuinely cross-file or repo-level finding, an
  explicit "no single file" marker rather than a path.
- **Severity** — exactly one of `P0` / `P1` / `P2`. **Informing only** (§2.7).
- **A short problem statement** — the finding `title` (what is wrong).
- **`evidence`** — the concrete behavior/text supporting the finding.
- **`impact`** — the engineering consequence.
- **The review target kind and its identifying metadata** — either the
  local implementation delta (`local-code-review`) or the Pull Request
  (`github-pr-review`); see
  [`../shared/policies/review-context.md`](../shared/policies/review-context.md),
  "The four concepts." **Informing only** (§5.5).
- **The current changed set for that target** — the diff / changed hunks and
  the ability to read the changed files at the reviewed revision.

### 4.2 Optional — present only in some reviews or for some findings

- **Precise line or line range.** A cross-cutting finding may carry only a
  section, a symbol, or a file-level location — see `location` in
  [`../shared/templates/finding.md`](../shared/templates/finding.md).
  **Informing only** (§4.3, §5.3).
- **Symbol / structural context** (enclosing function, class, method,
  module path). Availability depends on language and on the file not being
  classified opaque/generated/binary per
  [`../shared/policies/file-reviewability.md`](../shared/policies/file-reviewability.md).
- **Surrounding code context** beyond the changed lines (enough to read the
  defect in place).
- **`details`** — the optional longer explanation, per
  [`../shared/templates/finding.md`](../shared/templates/finding.md),
  "When a longer explanation is justified."
- **Location source annotation** — `local-code-review` only:
  `(committed)` / `(staged)` / `(unstaged)` / `(untracked)`. No PR
  equivalent exists. **Informing only** (§5.5).
- **Existing review evidence** — prior reviewer findings, resolved findings,
  and settled decisions, available only when an associated PR/reference is
  supplied (`local-code-review`) or prior reviews exist on the PR
  (`github-pr-review`); see
  [`../shared/policies/review-evidence.md`](../shared/policies/review-evidence.md).
  A prior finding *may* carry an identity assigned by an earlier run.
- **A previously reviewed SHA / prior review base** — available only on a
  same-reviewer delta re-review, per
  [`../skills/github-pr-review/policies/reviewer-delta-review.md`](../skills/github-pr-review/policies/reviewer-delta-review.md).
  Its recorded state, which commit is authoritative, and its invalidation
  are contracted in
  [`reviewed-sha-state-contract.md`](reviewed-sha-state-contract.md)
  ([#63](https://github.com/amirbena/code-review-skill/issues/63)); how a
  re-review computes the delta from it is
  [#64](https://github.com/amirbena/code-review-skill/issues/64). Neither
  is this document's concern.

### 4.3 Unavailable — MUST NOT be assumed

- A persistent per-finding identifier from an external tracker, database, or
  prior tool run that is not one of the inputs above.
- A stable, semantically meaningful **absolute line number** across
  revisions — line numbers move; identity MUST NOT be bound to one.
- **Full repository history / blame** beyond what the review target
  exposes, or history that survived a rewrite unchanged.
- A **semantic index, embeddings store, or language server** as a
  precondition — the current model does not provide one, and these
  requirements MUST be satisfiable without presupposing it.
- Any **runtime or execution observation** of the target (neither Skill
  runs target code).
- Any **cross-repository** signal — identity is single-repository only
  (§6, §8).
- **Volatile runtime signals** — wall-clock time, RNG, environment,
  worker/shard index, finding discovery order. §5.1–§5.2 forbid any
  dependence on these.

---

## 5. Stability requirements

This section is the authority on **which signals may determine identity**
and **how robust identity must be**. §4 lists what is *available*; this
section constrains what is *binding*.

1. **Deterministic.** For a fixed finding and a fixed target state, the
   identity value MUST always be the same — no dependence on wall-clock
   time, random seeds, machine, environment, or the number of review
   workers / shards (parallel execution is an optimization only; see
   [`../shared/policies/parallel-review.md`](../shared/policies/parallel-review.md)).
2. **Order-independent.** Identity MUST NOT depend on the order findings are
   discovered or emitted, or on how many other findings exist in the same
   review.
3. **Independent of volatile position.** Identity MUST NOT break solely
   because line numbers shifted, code was reindented, or unchanged
   defective code moved within its file (§2). Position MAY *inform*
   identity; it MUST NOT *be* the value.
4. **Stable across a normal re-review of the same change.** Re-running a
   review on the same PR / same local delta with no material change to the
   defective code MUST produce the same identity — including after commits
   that touched only unrelated files, after a rebase that left the code
   textually the same, and after the review base or HEAD SHA changed
   without changing the defect.
5. **Portable between the two Skills.** Identity is defined over the shared
   finding contract and MUST be computed only from inputs both Skills
   possess (§4.1, and §4.2 inputs only when present). Where an input is
   Skill-specific — the `local-code-review` repository-state annotation, or
   a PR HEAD SHA — identity MUST NOT depend on it such that the *same
   defect in the same change* resolves to different identities under
   `local-code-review` and under a later `github-pr-review` of the PR built
   from that work. **No identity-carrying findings handoff between the two
   Skills exists today**: `github-pr-review` does not ingest
   `local-code-review` output, and prior-review evidence reaches
   `local-code-review` only through a caller-supplied PR reference (§4.2).
   If such a handoff is introduced later, it MUST preserve identity
   unchanged.
6. **Consistent with the same-HEAD identity.** For a single unchanged
   state, the cross-review identity MUST NOT split two findings that
   [`../skills/github-pr-review/policies/pr-scope.md`](../skills/github-pr-review/policies/pr-scope.md)'s
   same-HEAD rule treats as one.
7. **Bounded sensitivity.** A small, behavior-preserving edit to the
   defective code — renaming a purely local identifier, extracting a
   sub-expression, a formatting change — SHOULD NOT by itself force a new
   identity while the defect is the same one. Identity MUST NOT be defined
   so tightly that the §2 scenarios fail.

---

## 6. Collision requirements

A **collision** is two *materially distinct* findings (per §3) receiving the
**same** identity.

- **Silent merge is unacceptable.** If two distinct defects collapse to one
  identity, the finding lifecycle
  ([#43](https://github.com/amirbena/code-review-skill/issues/43)) records
  them as one item; one real defect then rides on the other's history and
  can be marked resolved, suppressed as a duplicate, or hidden from a
  re-review. This is a correctness defect in the identity mechanism, not an
  acceptable approximation.
- **Required fail-safe direction: prefer splitting over merging.** When the
  mechanism is not confident two findings are the same, it MUST assign
  **distinct** identities. The asymmetry is deliberate:
  - a **false split** (the same defect looks new on re-review) produces a
    visible, measurable duplicate finding, recoverable by a human or by
    later tuning;
  - a **false merge** (two defects share one identity) is silent, can drop
    a real finding, and is not recoverable from the review output alone.

  Duplicate noise is a quality metric; a false merge is a safety failure.
- **Distinctness inputs MUST be honored.** Different program element,
  different defect behavior, and different location intent (§3) MUST be
  able to produce different identities even when file path and message text
  are identical.
- **No global-uniqueness claim.** Identity need not be a collision-free hash
  over all findings everywhere; the requirement is only that distinct
  findings in the same review context are never merged.

---

## 7. Ambiguity

When the mechanism **cannot confidently determine** whether a current
finding is the same as a prior one:

- It **MUST NOT** silently treat the match as definite.
- It **MUST resolve toward distinct** (§6): the current finding gets its own
  identity rather than adopting the prior one.
- It **SHOULD preserve the uncertainty for the lifecycle layer** — where the
  model can carry it, mark the pairing as a *low-confidence / candidate*
  relationship so
  [#43](https://github.com/amirbena/code-review-skill/issues/43) /
  [#62](https://github.com/amirbena/code-review-skill/issues/62) can decide
  conservatively. This document does not define that decision.
- It **MUST NOT auto-resolve.** An uncertain or absent match MUST NOT, on
  its own, cause a finding to be auto-resolved, auto-merged,
  auto-suppressed, or dropped from output.
- **Report, don't guess.** Consistent with
  [`../shared/policies/review-evidence.md`](../shared/policies/review-evidence.md)
  ("report that limitation rather than asserting it was handled"), when
  identity/matching completeness cannot be established, the review says so
  rather than implying reliable de-duplication.

---

## 8. Scope boundaries

This document defines **only** the identity contract above. It explicitly
does **not** define:

| Not defined here | Owner |
|---|---|
| Finding lifecycle states and transitions (`new` / `open` / `resolved` / `superseded` / `no longer applicable`) | [#62](https://github.com/amirbena/code-review-skill/issues/62), parent [#43](https://github.com/amirbena/code-review-skill/issues/43) |
| Reviewed-SHA state — what is recorded, where, and its invalidation | [`reviewed-sha-state-contract.md`](reviewed-sha-state-contract.md), [#63](https://github.com/amirbena/code-review-skill/issues/63) |
| Review delta / re-review semantics — how a re-review computes and acts on the change set | [#64](https://github.com/amirbena/code-review-skill/issues/64), [#65](https://github.com/amirbena/code-review-skill/issues/65) |
| Matching-strategy selection (structural hashing vs. fuzzy location vs. semantic similarity vs. hybrid) and its accuracy/cost trade-offs | [#59](https://github.com/amirbena/code-review-skill/issues/59) |
| The concrete identity derivation / serialization / hashing / any embedding use | [#60](https://github.com/amirbena/code-review-skill/issues/60) |
| Identity regression fixtures and their assertions | [#61](https://github.com/amirbena/code-review-skill/issues/61) |
| Cross-repository or cross-project finding identity | Out of scope for [#42](https://github.com/amirbena/code-review-skill/issues/42) entirely |
| Human-facing `F1` / `F2` display IDs and same-HEAD publish de-duplication | [`../shared/templates/finding.md`](../shared/templates/finding.md); [`../skills/github-pr-review/policies/pr-scope.md`](../skills/github-pr-review/policies/pr-scope.md) |

## Status and canonical home

**This document is the requirements record** for cross-review finding
identity. A downstream issue MAY refine it — explicitly, never by silent
divergence — if it discovers a genuine conflict between these requirements
and the shared review model.

[#60](https://github.com/amirbena/code-review-skill/issues/60) has landed the
**canonical deterministic derivation** of the stable identifier and its
descriptor primitives in
[`finding-stable-identity.md`](finding-stable-identity.md) (a
repository-development contract, with a test-only reference model). That
document owns *how* the identifier and primitives are constructed; this
document remains the authority on *what* identity must and must not do.

When a later issue
([#65](https://github.com/amirbena/code-review-skill/issues/65)) installs the
equivalent rule in a packaged resource (a `shared/policies/` file or an
extension of an existing one), **that policy becomes the single normative
source.** Both this document and
[`finding-stable-identity.md`](finding-stable-identity.md) then become
historical records: they MUST link to the canonical policy and MUST NOT keep
evolving the same rule independently.
