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
matching mechanism, and it is deliberately written so that structural
hashing, fuzzy location matching, semantic similarity, or a hybrid can each
still be evaluated against it in
[#59](https://github.com/amirbena/code-review-skill/issues/59).

This is a repository-development doc, like
[`runtime-parallelism.md`](runtime-parallelism.md): it is **not** packaged
into either Skill archive, and no packaged Skill resource depends on it.
When [#60](https://github.com/amirbena/code-review-skill/issues/60) ships a
runtime-normative rule, its canonical portable home is a packaged resource
(a `shared/policies/` file or an extension of an existing one), chosen then;
this doc becomes that rule's requirements record.

The finding fields these requirements are expressed over are the shared
finding contract in
[`../shared/templates/finding.md`](../shared/templates/finding.md).

---

## Summary

- **Identity tracks a defect, not a line and not a sentence.** Two findings
  share identity when they are the *same underlying problem in the same
  program element*, even if line numbers, surrounding code, or the
  reviewer's wording changed. They do **not** share identity merely because
  they sit on the same line or read similarly.
- **Stability is asymmetric on purpose.** Identity must survive
  movement/reformatting of otherwise-unchanged defective code, and must
  change when the defect, or the program element it lives in, is materially
  different.
- **Determinism is required.** The same finding against the same target
  state yields the same identity on every run, independent of discovery
  order or worker count.
- **Fail toward splitting, never toward merging.** When the mechanism
  cannot tell whether two findings are the same, it must treat them as
  distinct. A false split costs a re-surfaced duplicate (visible,
  recoverable); a false merge hides a real defect under another finding's
  record (silent, not recoverable).
- **No resolution behavior is defined here.** What a re-review *does* with a
  matched, unmatched, or uncertain identity — resolve, re-open, suppress,
  carry forward — belongs to the finding lifecycle
  ([#43](https://github.com/amirbena/code-review-skill/issues/43),
  [#62](https://github.com/amirbena/code-review-skill/issues/62)), not to
  this contract.

---

## 1. What finding identity represents

A **finding identity** is a value that answers one question across two
reviews of the same evolving change:

> Is *this* finding the same problem the earlier review already reported, or
> a different one?

It exists so a later review can distinguish "the same defect is still here"
from "a new defect appeared" without a human re-reading both reviews
side by side. It is the join key the finding lifecycle and delta/re-review
work build on; it is not itself a lifecycle state, a severity, or a
verdict.

### The four distinctions identity must get right

| Situation | Same identity? | Why |
|---|---|---|
| The **same underlying defect** is observed again — same faulty behavior, same root cause, same program element — after unrelated edits elsewhere | **Yes** | Identity follows the defect; incidental change around it does not create a new problem. |
| A second finding has **similar wording / rationale** to an earlier one but describes a **different underlying problem** | **No** | Identity is not text similarity. Two findings can be phrased almost identically and still be unrelated defects. |
| A finding sits at the **same file and line/range** as an earlier one but is a **different defect** (the original was fixed, or a new issue now occupies that location) | **No** | Location is a signal, not the identity. Same address, different problem = different finding. |
| The **same defect's code moved** — shifted by line-number changes, relocated within the file, reindented — while the defect itself is materially unchanged | **Yes** | Physical position is volatile; the defect is what persists. |

### Identity vs. the existing per-review and same-HEAD identifiers

Two related but different concepts already exist and are **not** what this
document specifies:

- **Human-facing display IDs (`F1`, `F2`, …)** in
  [`../shared/templates/finding.md`](../shared/templates/finding.md) are
  ordinals *within one review's output*. They are for reference in that one
  report and are not stable across runs.
- **`github-pr-review`'s same-HEAD deterministic identity** in
  [`../skills/github-pr-review/policies/pr-scope.md`](../skills/github-pr-review/policies/pr-scope.md),
  "Existing review awareness," is computed to suppress the *same workflow
  re-publishing the same finding for the same PR and the same HEAD*. It
  deliberately binds to the HEAD SHA and exact location and is not required
  to survive any code movement.

Cross-review finding identity is the **movement-tolerant superset**: it
must remain usable when the HEAD SHA changed and code moved. Its design
must stay *consistent with* the same-HEAD identity (two findings the
same-HEAD rule treats as identical must not be split by the cross-review
rule for the same unchanged state), but it is a distinct mechanism.
Reconciling the exact relationship between the two is in scope for
[#59](https://github.com/amirbena/code-review-skill/issues/59).

---

## 2. Must-survive scenarios (identity stays the same)

The defective code and the defect are materially unchanged; only the
surroundings or the presentation moved. Identity **must** be stable across
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
   Identity represents the defect, not its current severity label, so this
   alone should not produce a new identity. *(This is a deliberate
   difference from the same-HEAD identity in
   [`../skills/github-pr-review/policies/pr-scope.md`](../skills/github-pr-review/policies/pr-scope.md),
   which may fold severity in; how the cross-review rule relates to it is
   for [#59](https://github.com/amirbena/code-review-skill/issues/59).)*
8. **Cross-Skill re-review of the same change.** The change was reviewed
   once by `local-code-review` on the local delta and again by
   `github-pr-review` on the PR built from it (or vice versa). The same
   defect must carry the same identity across that hand-off — see
   **Portability** in §5.
9. **Re-review after a rebase or history rewrite of the branch** that leaves
   the defective code textually the same, even though commit SHAs and the
   review base changed.

Cross-check against the re-review change classes in
[#43](https://github.com/amirbena/code-review-skill/issues/43) /
[#64](https://github.com/amirbena/code-review-skill/issues/64):
**`unchanged`** and **`moved`** map to *stable identity*; **`reopened`**
(a previously fixed defect that regressed) must *reuse the original
identity* so the lifecycle can express a re-open rather than invent a new
problem.

---

## 3. Must-change scenarios (a new identity is required)

Textual or positional similarity must **not** collapse these into one
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
   reasons) must stay distinct.
5. **Same message text, different file or symbol.** Re-using a finding's
   phrasing at a new path or new element does not carry its identity there.
6. **Scope/intent of the finding changed.** A file-level or cross-cutting
   finding (no single line) and a line-specific finding in the same file are
   different findings even if they touch the same concern, because their
   location intent differs.

`newly introduced` in
[#43](https://github.com/amirbena/code-review-skill/issues/43) always maps
to a *fresh identity*.

**Guard against equating text similarity with identity.** A mechanism that
keys primarily on normalized message text will fail scenarios 1, 2, and 4
here. A mechanism that keys primarily on file+line will fail scenario 3
here and scenarios 1–5 in §2. The requirements intentionally push toward
identifying *the defect in its program element*, and leave *how* to
[#59](https://github.com/amirbena/code-review-skill/issues/59).

---

## 4. Inputs available at review time

An identity mechanism may rely only on signals that actually exist in this
repository's review model. The finding fields are those in
[`../shared/templates/finding.md`](../shared/templates/finding.md); the
target/context concepts are those in
[`../shared/policies/review-context.md`](../shared/policies/review-context.md)
and
[`../shared/policies/review-evidence.md`](../shared/policies/review-evidence.md).

### 4.1 Guaranteed — always present for any actionable finding

- **Repository-relative file path** of the finding (normalized;
  `/`-separated). For a genuinely cross-file or repo-level finding, an
  explicit "no single file" marker rather than a path.
- **Severity** — exactly one of `P0` / `P1` / `P2`.
- **A short problem statement** — the finding `title` (what is wrong).
- **`evidence`** — the concrete behavior/text supporting the finding.
- **`impact`** — the engineering consequence.
- **The review target kind and its identifying metadata** — either the
  local implementation delta (`local-code-review`) or the Pull Request
  (`github-pr-review`); see
  [`../shared/policies/review-context.md`](../shared/policies/review-context.md),
  "The four concepts."
- **The current changed set for that target** — the diff / changed hunks and
  the ability to read the changed files at the reviewed revision.

### 4.2 Optional — present only in some reviews or for some findings

- **Precise line or line range.** A cross-cutting finding may carry only a
  section, a symbol, or a file-level location — see `location` in
  [`../shared/templates/finding.md`](../shared/templates/finding.md).
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
  equivalent exists.
- **Existing review evidence** — prior reviewer findings, resolved findings,
  and settled decisions, available only when an associated PR/reference is
  supplied (`local-code-review`) or prior reviews exist on the PR
  (`github-pr-review`); see
  [`../shared/policies/review-evidence.md`](../shared/policies/review-evidence.md).
  A prior finding *may* carry an identity assigned by an earlier run.
- **A previously reviewed SHA / prior review base** — available only on a
  same-reviewer delta re-review, per
  [`../skills/github-pr-review/policies/reviewer-delta-review.md`](../skills/github-pr-review/policies/reviewer-delta-review.md).
  Its storage and semantics are
  [#63](https://github.com/amirbena/code-review-skill/issues/63) /
  [#64](https://github.com/amirbena/code-review-skill/issues/64), not this
  document.

### 4.3 Unavailable — must not be assumed

- A persistent per-finding identifier from an external tracker, database, or
  prior tool run that is not one of the inputs above.
- A stable, semantically meaningful **absolute line number** across
  revisions — line numbers move and must not be the sole identity signal.
- **Full repository history / blame** beyond what the review target
  exposes, or history that survived a rewrite unchanged.
- A **semantic index, embeddings store, or language server** as a
  precondition — the current model does not provide one.
  [#59](https://github.com/amirbena/code-review-skill/issues/59) may
  *recommend* introducing such a capability, but these requirements must be
  satisfiable without presupposing it.
- Any **runtime or execution observation** of the target (neither Skill
  runs target code).
- Any **cross-repository** signal — identity is single-repository only
  (§6).
- Wall-clock time, RNG, environment, worker/shard index, or finding
  discovery order (§5).

---

## 5. Stability requirements

1. **Deterministic.** For a fixed finding and a fixed target state, the
   identity value is always the same. No dependence on wall-clock time,
   random seeds, machine, environment, or the number of review workers /
   shards used (parallel execution is an optimization only — see
   [`../shared/policies/parallel-review.md`](../shared/policies/parallel-review.md)).
2. **Order-independent.** Identity does not depend on the order findings are
   discovered or emitted, or on how many other findings exist in the same
   review.
3. **Independent of volatile position where possible.** Identity must not
   break solely because line numbers shifted, code was reindented, or
   unchanged defective code moved within its file (§2). Position may
   *inform* identity; it may not be the value.
4. **Stable across a normal re-review of the same change.** Re-running a
   review on the same PR / same local delta with no material change to the
   defective code produces the same identity — including after commits that
   touched only unrelated files, after a rebase that left the code
   textually the same, and after the review base or HEAD SHA changed
   without changing the defect.
5. **Portable between the two Skills.** Identity is defined over the shared
   finding contract and computed only from inputs both Skills possess
   (§4.1, and §4.2 inputs only when actually present). Where an input is
   Skill-specific — the `local-code-review` repository-state annotation, or
   a PR HEAD SHA — identity must not depend on it in a way that makes the
   *same defect in the same change* resolve to different identities under
   `local-code-review` and under a later `github-pr-review` of the PR built
   from that work. The
   [handoff between the two Skills](ARCHITECTURE.md) must preserve identity.
6. **Consistent with the same-HEAD identity.** For a single unchanged
   state, the cross-review identity must not split two findings that
   [`../skills/github-pr-review/policies/pr-scope.md`](../skills/github-pr-review/policies/pr-scope.md)'s
   same-HEAD rule treats as one.
7. **Bounded sensitivity.** A small, behavior-preserving edit to the
   defective code (rename of a purely local identifier, extraction of a
   sub-expression, a formatting change) should not, by itself, be required
   to change identity when the defect is still the same one. The exact
   tolerance is a design question for
   [#59](https://github.com/amirbena/code-review-skill/issues/59); the
   requirement here is only that identity is *not* defined so tightly that
   §2 scenarios fail.

---

## 6. Collision requirements

A **collision** is two *materially distinct* findings (per §3) receiving the
**same** identity.

- **Unacceptable outcome: silent merge.** If two distinct defects collapse
  to one identity, the finding lifecycle
  ([#43](https://github.com/amirbena/code-review-skill/issues/43)) records
  them as one item. One real defect then rides on the other's history and
  can be marked resolved, suppressed as a duplicate, or hidden from a
  re-review because its "record" already exists. This must be treated as a
  correctness defect in the identity mechanism, not an acceptable
  approximation.
- **Required fail-safe direction: prefer splitting over merging.** When the
  mechanism is not confident two findings are the same, it must assign
  **distinct** identities.
  - A **false split** (the same defect looks new on re-review) produces a
    visible duplicate/re-surfaced finding. It is annoying and measurable,
    and it is recoverable by a human or by later tuning.
  - A **false merge** (two defects share one identity) is silent and can
    drop a real finding. It is not recoverable from the review output
    alone.
  The asymmetry is deliberate: **duplicate noise is a quality metric;
  a false merge is a safety failure.** This direction is fixed here; the
  *technique* that achieves it is
  [#59](https://github.com/amirbena/code-review-skill/issues/59) /
  [#60](https://github.com/amirbena/code-review-skill/issues/60).
- **Distinctness inputs must be honored.** Different program element,
  different defect behavior, and different location intent (§3) must be
  capable of producing different identities even when file path and message
  text are identical.
- **No global-uniqueness claim.** These requirements do not mandate that
  identity be a collision-free hash over all findings everywhere; they
  mandate that *distinct findings in the same review context* are not
  merged and that ambiguity resolves toward distinctness.

---

## 7. Ambiguity

When the mechanism **cannot confidently determine** whether a current
finding is the same as a prior one:

- **Do not silently treat it as the same.** An uncertain match must not be
  presented as a definite match.
- **Resolve toward distinct** (§6): assign the current finding its own
  identity rather than adopting the prior one.
- **Preserve the uncertainty for the lifecycle layer.** Where the model can
  carry it, the pairing should be marked as a *low-confidence / candidate*
  relationship so
  [#43](https://github.com/amirbena/code-review-skill/issues/43) /
  [#62](https://github.com/amirbena/code-review-skill/issues/62) can decide
  conservatively. This document does **not** define what that decision is.
- **No automatic resolution behavior is defined here.** An uncertain or
  absent match must not, on its own, cause a finding to be auto-resolved,
  auto-merged, auto-suppressed, or dropped from output. Anything that would
  make later lifecycle logic unsafe is out of bounds for the identity
  mechanism.
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
| Reviewed-SHA state — what is persisted, where, and its invalidation | [#63](https://github.com/amirbena/code-review-skill/issues/63) |
| Review delta / re-review semantics — how a re-review computes and acts on the change set | [#64](https://github.com/amirbena/code-review-skill/issues/64), [#65](https://github.com/amirbena/code-review-skill/issues/65) |
| Matching-strategy selection (structural hashing vs. fuzzy location vs. semantic similarity vs. hybrid) and its accuracy/cost trade-offs | [#59](https://github.com/amirbena/code-review-skill/issues/59) |
| The concrete identity derivation / serialization / hashing / any embedding use | [#60](https://github.com/amirbena/code-review-skill/issues/60) |
| Identity regression fixtures and their assertions | [#61](https://github.com/amirbena/code-review-skill/issues/61) |
| Cross-repository or cross-project finding identity | Out of scope for [#42](https://github.com/amirbena/code-review-skill/issues/42) entirely |
| Human-facing `F1` / `F2` display IDs and same-HEAD publish de-duplication | [`../shared/templates/finding.md`](../shared/templates/finding.md); [`../skills/github-pr-review/policies/pr-scope.md`](../skills/github-pr-review/policies/pr-scope.md) |

A downstream issue may refine wording here if it discovers a genuine
conflict with the shared review model — it should do so explicitly, not by
silently diverging.
