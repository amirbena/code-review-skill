# Stacked PR / Dependent-Change Review — Contract

Repository-development contract for GitHub Issue
[#119](https://github.com/amirbena/code-review-skill/issues/119). It defines
the review flow's understanding of **stacked / dependent PR topology**: how
to select the **effective review base** of a stack layer, how to distinguish
that layer's **owned delta** from **inherited (lower-stack) delta**, which
SHA(s) must be persisted for reliable re-review, what triggers a partial vs.
full re-review of an upper layer when a lower layer changes, and how
ambiguous or broken stack topology fails safely.

This document is **contract / requirements only**, in the same repository-
development-record sense as
[#63](https://github.com/amirbena/code-review-skill/issues/63)'s
[`reviewed-sha-state-contract.md`](reviewed-sha-state-contract.md), which
remains an active contract record. Its
[#64](https://github.com/amirbena/code-review-skill/issues/64) sibling,
[`delta-re-review-contract.md`](delta-re-review-contract.md), has already
progressed one stage further along that same lifecycle: since
[#65](https://github.com/amirbena/code-review-skill/issues/65) installed
the equivalent runtime behavior, that document is now a **historical
design record**, and the single normative source for delta re-review
semantics is the packaged policy
[`stateful-delta-rereview.md`](../../skills/github-pr-review/policies/stateful-delta-rereview.md).
This document does not implement stack detection, re-derive existing
base/head-fidelity mechanics, or redefine finding identity, matching, or
lifecycle. Wherever a section below stops at "enough state for a
downstream pass to decide," that decision belongs to #65's analogue for
stacked-PR review — a future stacked-review implementation issue — not to
this document.

This is a repository-development doc, like
[`reviewed-sha-state-contract.md`](reviewed-sha-state-contract.md) and
[`delta-re-review-contract.md`](delta-re-review-contract.md): it is **not**
packaged into either Skill archive, and no packaged Skill resource depends
on it. Its standing relative to an eventual runtime policy is defined in
"Status and canonical home" at the end.

This contract **reuses, and does not redefine**:

- the Reviewed State Record and its fields, authoritative-SHA rule, and
  reviewer-ownership discipline —
  [`reviewed-sha-state-contract.md`](reviewed-sha-state-contract.md) (#63);
- change classes, blast-radius attribution, settled-assumption
  reconsideration, and the semantic escalation triggers —
  [`delta-re-review-contract.md`](delta-re-review-contract.md) (#64), now
  a historical design record whose canonical semantics live in
  [`stateful-delta-rereview.md`](../../skills/github-pr-review/policies/stateful-delta-rereview.md)
  (#65) (see "Status and canonical home" below);
- lifecycle states/events (`OPEN`/`RESOLVED`;
  `DETECTED`/`STILL_PRESENT`/`RESOLVED`/`REOPENED`/`UNCERTAIN`) and
  finding-identity/matching outcomes
  (`MATCH`/`NO MATCH`/`AMBIGUOUS`) —
  [`finding-lifecycle-contract.md`](finding-lifecycle-contract.md) (#62),
  [`finding-identity-requirements.md`](finding-identity-requirements.md)
  (#58), [`finding-matching-strategy.md`](finding-matching-strategy.md)
  (#59) — vocabulary only, no redefinition;
- Review Target / Review Context / Repository Context / Existing Review
  Evidence —
  [`../../shared/policies/review-context.md`](../../shared/policies/review-context.md);
- one review scope → one owner —
  [`../../shared/policies/review-ownership.md`](../../shared/policies/review-ownership.md);
- base/head fidelity mechanics (resolving base ref/SHA, head ref/SHA,
  merge-base, and "base advanced after the branch was cut") —
  [`../../skills/github-pr-review/policies/repository-checkout.md`](../../skills/github-pr-review/policies/repository-checkout.md),
  "Base / head fidelity."

Relates: [#43](https://github.com/amirbena/code-review-skill/issues/43),
[#63](https://github.com/amirbena/code-review-skill/issues/63),
[#64](https://github.com/amirbena/code-review-skill/issues/64),
[#72](https://github.com/amirbena/code-review-skill/issues/72).

---

## Canonical invariant

> **A stack layer's review base is its own declared parent, never an
> assumed default/target branch — and content already present in that
> parent is read-only context for this layer, never a finding this layer
> owns.**

Everything below is an elaboration of that one sentence. Stacked-PR support
is not a new base-derivation algorithm; it is the existing base/head
fidelity discipline
([`repository-checkout.md`](../../skills/github-pr-review/policies/repository-checkout.md))
applied without the (previously implicit) assumption that "the base" always
means the repository's default/target branch.

---

## 1. Terminology and ownership

- **Stack** — an ordered chain of branches/PRs where each PR's declared
  base ref is another PR's branch, terminating at the repository's
  default/target branch (the **root**): `root -> PR A -> PR B -> PR C`.
- **Layer** — one PR in the stack. Layer 0 is the root (not a PR); layer
  `N` is the `N`-th PR counted from the root.
- **Effective review base** of layer `N` — layer `N`'s PR's own declared
  base ref, resolved to its SHA **at review time**, per the existing base
  resolution rule in
  [`repository-checkout.md`](../../skills/github-pr-review/policies/repository-checkout.md).
  When layer `N`'s base is layer `N-1`'s branch, the effective review base
  *is* layer `N-1`'s current head — never the root, and never assumed to
  be the root merely because that is the common case.
- **Owned delta** of layer `N` — the change this layer's review is
  responsible for and may report findings against:
  `merge-base(effective_base_head, layer_N_head) .. layer_N_head`. This is
  ordinary PR-delta math (identical to
  [`repository-checkout.md`](../../skills/github-pr-review/policies/repository-checkout.md),
  "Base / head fidelity"); the only thing stacked-PR support changes is
  which SHA gets called "the base."
- **Inherited delta** of layer `N` — everything present in the effective
  review base but not in the root: recursively, `layer 1`'s owned delta +
  `layer 2`'s owned delta + … + `layer N-1`'s owned delta. Layer `N`'s
  reviewer never has to compute this separately layer-by-layer — it is,
  by construction, whatever code already exists in the effective review
  base. It is **Repository Context**
  ([`../../shared/policies/review-context.md`](../../shared/policies/review-context.md)),
  read to judge correctness and invariants, never promoted to Review
  Target. A pre-existing condition inside the inherited delta is not a
  finding this layer's review reports — exactly as
  [`repository-checkout.md`](../../skills/github-pr-review/policies/repository-checkout.md),
  "Repository Context must not widen the Review Target," already requires
  for any surrounding code a reviewer reads for context.
- **Root** — the repository's default/target branch, where the stack
  terminates. A PR whose declared base already is the root is **not** a
  stacked layer under this contract; it is an ordinary single-layer review
  and every existing #63/#64 rule applies unchanged.
- **Topology** — the shape of the stack as derived from declared base refs
  and open-PR state. "Broken" or "ambiguous" topology is a topology this
  contract cannot resolve safely — see §5.

## 2. Effective base selection rule

1. Resolve the PR's declared base ref and SHA exactly as
   [`repository-checkout.md`](../../skills/github-pr-review/policies/repository-checkout.md)
   already requires — never assume the local default/target branch equals
   the declared base.
2. If the declared base **is** the repository's default/target branch,
   this PR is layer 1 of a one-layer "stack" (i.e., an ordinary,
   non-stacked review). Stop; no further chain-walking is needed.
3. If the declared base is **not** the default/target branch, this PR is a
   stack layer whose immediate parent is that base branch. Determine
   whether the base branch itself corresponds to another **open PR**
   against this repository:
   - If it does, that PR is layer `N-1`; recurse from step 1 using that
     PR's own declared base, building the chain upward until step 2 stops
     it at the root, or until resolution fails (§5).
   - If the base branch does **not** correspond to any open PR (e.g. an
     unreviewed shared integration branch, or the parent PR was already
     merged/closed — see §5, "Closed or merged lower PR"), treat the base
     branch itself as the effective review base for this layer without
     assuming it is, or is not, a stack layer; its own further ancestry is
     not walked past this point unless a further open PR is found.
4. The effective review base for the layer under review is the **immediate
   parent's current head SHA** — never a bare guess, never the root,
   never "whatever `main` happens to point at."

This rule introduces no new git mechanics. It only requires that the
existing base-resolution step never substitute the default/target branch
for the PR's actual declared base — which is precisely the failure mode
the parent Issue describes ("reviewing B against `main` incorrectly pulls
in A's changes").

## 3. Owned vs. inherited delta

Because the owned delta is computed against the effective review base
(§2), not the root, ordinary PR-delta math already yields the correct
scope — duplicate findings, inflated scope, and wrong attribution are
prevented by using the right base, not by a separate filtering step.

- **Owned delta** is the Review Target for layer `N`. Every finding this
  layer's review reports must be causally connected to this range, exactly
  as [`repository-checkout.md`](../../skills/github-pr-review/policies/repository-checkout.md)
  already requires for any PR review.
- **Inherited delta** is Repository Context. It may be read to understand
  interfaces, invariants, and surrounding behavior the owned delta
  interacts with (including via #64 blast-radius attribution, §4 below),
  but a defect whose only causal site is inside the inherited delta, with
  no attributable connection to the owned delta, is **not** a finding this
  layer's review owns. It belongs to the layer that actually owns that
  code (layer `N-1`'s own review, present or past).
- **Blast radius still applies across the boundary.** If layer `N`'s owned
  delta causally interacts with inherited code (e.g., it calls a function
  A introduced, or changes a shared type A also touches), that interaction
  is evaluated with the same evidence-based blast-radius rule as any other
  case in
  [`delta-re-review-contract.md`](delta-re-review-contract.md) §4 — the
  owned/inherited boundary changes *whose* code a defect's root cause sits
  in, never whether an evidenced, delta-attributable defect gets reported.

### Worked example: three-layer stack

`root(main) -> PR A -> PR B -> PR C`, each PR adding one small increment.

- **Layer 1 (PR A)** — base = `main`. Ordinary, non-stacked review. Owned
  delta = `merge-base(main, A) .. A`. No inherited delta.
- **Layer 2 (PR B)** — declared base = A's branch. Effective review base =
  A's current head. Owned delta = `merge-base(A_head, B_head) .. B_head`
  — exactly B's own commits, not A's. Inherited delta = everything in A's
  branch not yet in `main` (i.e., A's owned delta, read as context). If A
  introduced a helper function with a latent off-by-one bug that B's code
  never calls, B's review does not report it — that is A's review's
  finding, not B's. If B's new code calls that helper in a way that
  exposes the bug through a path A's review could not have anticipated,
  §4's blast-radius rule makes that a legitimate finding *for B's review*
  (the causal site of the newly exposed failure is the interaction B's
  delta introduced), while the underlying bug in A's own code remains
  A's attribution.
- **Layer 3 (PR C)** — declared base = B's branch. Effective review base =
  B's current head. Owned delta = `merge-base(B_head, C_head) .. C_head`.
  Inherited delta = everything in B's branch not yet in `main` (A's
  changes **and** B's changes, uniformly — C's reviewer does not need to
  know or care that two layers, rather than one, contributed the inherited
  code; it is all Repository Context).

## 4. Persisted SHA(s) for reliable re-review

This contract does **not** introduce a second, parallel state record. A
stack layer's Reviewed State Record is the same
[Reviewed State Record](reviewed-sha-state-contract.md) #63 already
defines, populated as follows:

- **Base branch name** (#63 field, unchanged) — for a stack layer, this is
  the immediate parent's branch name (e.g. `feature/pr-a`), not the root.
- **Base SHA at review time** (#63 field, unchanged) — for a stack layer,
  this is the immediate parent's head SHA at review time (§2), not the
  root's tip. This is exactly the field #63 already asks a re-review to
  compare against to detect "the base moved" — a stack layer's base moving
  and the root moving are the *same mechanism*, just applied one level
  removed from the root.
- **Merge-base SHA at review time** (#63 field, unchanged) — computed
  between the effective review base and the reviewed head, as usual.
- **One additional, stacking-specific datum: effective-base provenance.**
  Record whether the effective review base is the repository's
  default/target branch (root) or another open PR, and — when it is
  another open PR — that PR's identity (number/URL). This is an
  **annotation on the existing base-branch-name field**, not a new
  parallel record: it lets a later pass distinguish "the base is `main`
  and moved" from "the base is PR A and PR A itself may have changed,
  been retargeted, or been merged/closed" (§5), which needs a different
  invalidation check than a simple branch-tip comparison.

No other new field is required. The reviewed head SHA, reviewer identity,
review result, completeness, prior reviewed SHA, provenance marker, and
optional evidence reference are all populated exactly as #63 specifies,
unchanged.

## 5. A lower PR changes after an upper PR was reviewed

**Trigger condition.** The recorded effective-base SHA (§4) for layer `N`
no longer matches layer `N-1`'s **current** head SHA. This is the
stack-layer instance of #63 §3's "base branch advanced" case — the
mechanism is identical; only the fact that "the base" here is another PR,
not the root, is new.

Resolving this trigger reuses the same escalation model
[`delta-re-review-contract.md`](delta-re-review-contract.md) (#64)
records and [`stateful-delta-rereview.md`](../../skills/github-pr-review/policies/stateful-delta-rereview.md)
(#65) now normatively implements — it does not invent a second one:

| Condition on layer `N-1`'s new commits (relative to layer `N`'s recorded effective-base SHA) | Effect on layer `N`'s re-review |
|---|---|
| Layer `N-1`'s recorded head SHA is still an ancestor of its new head (ordinary forward progress, no rebase), **and** the new commits have no #64 §4 blast-radius attribution into layer `N`'s owned delta | **No re-review required.** Layer `N`'s Reviewed State Record for its own owned delta stays valid. Only the *inherited-context view* is stale and should be refreshed (re-read, not re-reviewed) the next time layer `N` is reviewed for any other reason. |
| Same ancestry condition, **but** the new commits are #64 §4 blast-radius attributable into layer `N`'s owned delta (a shared interface, type, or config the owned delta depends on changed underneath it) | **Partial (bounded delta) re-review** of layer `N`, scoped to the blast-radius interaction — an ordinary #64 delta re-review trigger, applied across the layer boundary exactly as it would apply to any other code the owned delta causally touches. |
| Layer `N-1`'s recorded head SHA is **no longer an ancestor** of its new head (rebase, force-push, or history rewrite on the lower layer) | **Escalate to a full review** of layer `N`. Per #63 §2/§7, an unreachable/non-ancestor prior SHA invalidates the assumptions the earlier review of layer `N` made about *what it had already accounted for as inherited* — a bounded delta cannot be trusted to reconstruct that. This mirrors #64 §7's "Reviewed-state preconditions are violated" escalation trigger. |

No numeric threshold is introduced, matching #64 §7's own refusal to
invent one — the trigger is evidence-based (ancestry check, blast-radius
attribution), not a count of changed files or lines.

## 6. Safe failure for ambiguous or broken topology

**Guiding principle**, restating #63 §7 / #64 §7's existing "fail
conservative" discipline for this contract: *when the stack topology, or a
layer's relationship to it, cannot be resolved safely, fail closed to a
**wider**, never a narrower, review scope.* Under-scoping a review can
silently hide a real defect (attributing it to a layer that never actually
reviews it); over-scoping only costs redundant effort and is always safe.
This is the same asymmetry #64's canonical invariant already states for
ordinary delta re-review, applied one level up to stack-topology
detection.

Two fallback tiers, from narrowest to widest safe scope:

### Tier 1 — single-hop fallback (topology detail unresolved, immediate base still trustworthy)

Applies when the *stack chain beyond the immediate parent* cannot be
resolved cleanly, but the PR's own declared base ref and SHA are still
trustworthy: the merge-base between the effective base and the current
head cannot be resolved to a single unambiguous commit (criss-cross
merges / an octopus/multi-parent merge on the boundary), or it cannot be
determined with confidence whether the immediate base branch corresponds
to a further open PR.

**Fallback:** treat this layer as an **ordinary, single-hop PR review**
against its own currently declared base ref/SHA (§2), exactly as if no
deeper stack were being detected. This is always safe: the layer's owned
delta computed this way is never wrong (it is the same PR-delta math every
non-stacked review already trusts), and it only foregoes the *display*
convenience of showing further stack layers below it. It never resolves
into pulling more content into the owned delta than the immediate base
justifies.

### Tier 2 — root fallback (the relationship itself is broken)

Applies when even the single-hop relationship cannot be trusted:

- **Rebase / force-push on the current layer itself** — per #63 §2/§7,
  the prior reviewed state is invalidated; a **fresh full review** of the
  new head is performed. This is the existing #63 rule; stacking adds
  nothing new here.
- **Changed parent branch (retarget)** — the PR's declared base ref itself
  changed (e.g. it now points at `main` instead of PR A's branch, or at a
  different PR entirely). Per #63 §7 ("Base context is incompatible"),
  any reviewed state recorded against the *old* base is invalidated. The
  *newly* declared base is not itself an error — it is simply re-derived
  from current state (§2) as the effective base for a fresh review; no
  guessing which of the old or new base is "correct" is performed.
- **Closed or merged lower PR** — layer `N-1`'s PR has merged or closed.
  Two sub-cases:
  - The merge was a fast-forward or an ordinary (non-squash, non-rebase)
    merge, so layer `N-1`'s original commits are still present, unchanged,
    as ancestors of the root. Layer `N`'s branch's relationship to the
    root is unaffected in substance; re-deriving the effective base per
    §2 naturally resolves to the root once layer `N-1`'s branch no longer
    corresponds to an open PR and is itself fully merged into the root.
    No broken-topology fallback is needed.
  - The merge was a **squash or rebase merge** (this repository's own
    default merge strategy per
    [`../../policies/git-pr-merge-policy.md`](../../policies/git-pr-merge-policy.md)),
    so layer `N-1`'s original commits do **not** appear, byte-for-byte, in
    the root. Layer `N`'s branch, still built on the original (now
    "orphaned" relative to the root) commits, no longer has a clean
    ancestor relationship to the root: a naive `merge-base(root, layer_N_head)`
    would resolve to a point *before* layer `N-1` even started, making
    **all** of layer `N-1`'s original changes appear to be part of layer
    `N`'s diff against the root. This is a genuine desync, not a
    resolvable single-hop case. **Fallback:** full review of layer `N`'s
    current head against the root, with the stack display (§7) explicitly
    reporting the topology as unresolved/desynced and recommending the
    layer be rebased onto the root before further stacked review is
    reliable. Reviewing the wider (now-stale) scope is the safe direction:
    it never hides a defect, and it makes the desync visible to a human
    rather than silently misattributing already-reviewed content as new.
- **Cycle or otherwise malformed chain** (e.g. base refs that resolve
  circularly, or a chain that cannot be walked to the root within a
  reasonable bound) — this is nonsensical topology, not an ordinary
  edge case. **Fallback:** full review of the current head against the
  **root** (the repository's actual default/target branch), with the
  stack explicitly reported as "topology undetermined." No arbitrary
  point in the cycle is picked as "the" effective base — that would be
  guessing.

In every Tier 2 case, "full review against the root" may review some
content that a correctly resolved stack would have excluded as inherited.
That is the accepted cost of failing safely: it never silently drops a
defect, and it never fabricates an owned/inherited split the topology
does not actually support.

## 7. Review output

The review output must show, for the layer under review:

- the detected stack, root to current layer (e.g.
  `main -> PR A -> PR B -> PR C`), or an explicit statement that no deeper
  stack was detected / the topology fell back per §6;
- which layer is currently under review (e.g. "reviewing layer 3 of 3:
  PR C");
- the effective review base actually used (branch/PR identity and SHA),
  distinct from the repository's default/target branch when they differ;
- when a Tier 1 or Tier 2 fallback (§6) was applied, which one and why,
  so a human reviewer understands the scope was widened rather than
  silently narrowed.

This is a presentation/contract requirement on what the output must
convey, not a UI or template implementation — the concrete rendering is
left to the same downstream implementation issue that installs this
contract's runtime behavior (see "Status and canonical home"), consistent
with how #63/#64's own "reporting" requirements are worded contractually
here and implemented later in
[`../../skills/github-pr-review/policies/stateful-delta-rereview.md`](../../skills/github-pr-review/policies/stateful-delta-rereview.md).

---

## Required examples

Shared setup: repository root branch `main`, reviewer `R` unless stated.

### A. Three-layer stack, owned delta scoped correctly

See "Worked example: three-layer stack" in §3 above — PR C's review
reports findings only from `merge-base(B_head, C_head)..C_head`; A's and
B's own changes are read as context, never as C's findings.

### B. Lower PR changes after upper PR reviewed — no re-review needed

1. `root -> PR A -> PR B`. B is reviewed; effective-base SHA for B is
   recorded as A's head at that time (`A0`).
2. A advances to `A1` (new commits), touching a part of A's code B's
   owned delta never calls and has no blast-radius attribution into.
3. Per §5 row 1: B's recorded reviewed state is still valid. No re-review
   of B is triggered; only B's inherited-context view is stale until B is
   next reviewed for another reason.

### C. Lower PR changes after upper PR reviewed — partial re-review

1. Same setup as B, but A's new commits (`A0 -> A1`) change a shared
   interface B's owned delta calls directly.
2. Per §5 row 2: this is #64 §4 blast-radius attributable. A **partial**
   (bounded delta) re-review of B is triggered, scoped to the interaction
   with the changed interface — not a full review of all of B.

### D. Lower PR rebased after upper PR reviewed — full re-review

1. Same setup as B, but A is rebased; A's previously recorded head `A0`
   is no longer an ancestor of A's new head `A1'`.
2. Per §5 row 3: B's recorded effective-base SHA is invalidated (mirrors
   #63 §2/§7's rebase handling). A **full review** of B is required — a
   bounded delta cannot safely reconstruct what B's prior review actually
   accounted for as "already inherited" from A.

### E. Ambiguous merge-base — Tier 1 fallback

1. `root -> PR A -> PR B`, but a criss-cross merge on B's branch makes
   `merge-base(A_head, B_head)` resolve to more than one plausible commit.
2. Per §6 Tier 1: B is reviewed as an ordinary single-hop PR against its
   own currently declared base ref/SHA. The deeper stack display is
   omitted or marked undetermined; B's owned delta is still computed
   correctly from its own declared base.

### F. Squash-merged lower PR — Tier 2 fallback

1. `root -> PR A -> PR B`. PR A is squash-merged into `main`; A's original
   commits do not appear in `main`.
2. B's branch, still built on A's original (pre-squash) commits, no longer
   has a clean ancestor relationship to `main`.
3. Per §6 Tier 2, "Closed or merged lower PR": full review of B against
   `main` is performed. The output explicitly reports the topology as
   desynced and recommends rebasing B onto `main`. B's owned delta as
   computed this way may include A's already-reviewed changes as an
   artifact of the desync — an accepted, safe-direction cost, never a
   silently dropped finding.

### G. Cyclic / malformed chain — Tier 2 fallback

1. Branch refs are misconfigured such that PR X's declared base resolves,
   through the chain, back to PR X itself (or the chain cannot be walked
   to `main` within a reasonable bound).
2. Per §6 Tier 2, "Cycle or otherwise malformed chain": full review
   against `main` is performed; the stack is reported as
   "topology undetermined." No arbitrary point in the cycle is guessed as
   the effective base.

---

## Status and canonical home

[#119](https://github.com/amirbena/code-review-skill/issues/119) has
implemented stacked/dependent-PR review at runtime. The canonical runtime
rule now lives in the packaged policy
[`skills/github-pr-review/policies/stacked-pr-review.md`](../../skills/github-pr-review/policies/stacked-pr-review.md);
that policy is the single normative source for stack-topology detection,
effective-base derivation, owned-vs-inherited delta scoping, safe-failure
fallback, and the lower-layer re-review trigger, and **this document is
now a historical design record** — it must not evolve the same rules
independently, only link to the canonical policy.

**Existing canonical contracts are unchanged and remain authoritative for
what they already own.** This document adds the stack-topology layer on
top of them; it does not restate or override:

- [`reviewed-sha-state-contract.md`](reviewed-sha-state-contract.md) (#63)
  — the Reviewed State Record fields §4 above populates for a stack layer,
  the authoritative-SHA rule, and reviewer ownership;
- [`delta-re-review-contract.md`](delta-re-review-contract.md) (#64), now
  a historical design record whose canonical semantics live in
  [`stateful-delta-rereview.md`](../../skills/github-pr-review/policies/stateful-delta-rereview.md)
  (#65) — change classes, blast-radius attribution, and the semantic
  escalation triggers §5 and §6 reuse unchanged;
- [`../../skills/github-pr-review/policies/repository-checkout.md`](../../skills/github-pr-review/policies/repository-checkout.md)
  — base/head fidelity mechanics this contract applies without a new
  algorithm;
- [`../../shared/policies/review-context.md`](../../shared/policies/review-context.md)
  and
  [`../../shared/policies/review-ownership.md`](../../shared/policies/review-ownership.md)
  — the Review Target / Repository Context distinction §3 relies on, and
  the one-owner-per-scope invariant (a stack's layers are still reviewed
  by whichever `github-pr-review` invocation owns each individual PR;
  this contract does not introduce a single reviewer owning an entire
  stack).

This is a repository-development doc, like its siblings in this
directory: **not** packaged into either Skill archive, and no packaged
Skill resource depends on it (see [`../../AGENTS.md`](../../AGENTS.md),
"Packaged Skills are independent of repository-level instructions"). It
remains contract-record framing for the sections above; only this
"Status and canonical home" section is updated to point at the installed
runtime policy — the same lifecycle already described for
[`finding-identity-requirements.md`](finding-identity-requirements.md),
[`reviewed-sha-state-contract.md`](reviewed-sha-state-contract.md), and
[`delta-re-review-contract.md`](delta-re-review-contract.md), which
remain contract records until their own installing issues land.

## Scope boundaries

This document defines **only** the stacked-PR review contract above. It
explicitly does **not** define:

| Not defined here | Owner |
|---|---|
| Runtime stack detection (querying the GitHub API for open PRs by base ref, walking the chain in code) | A future implementation issue, analogous to #65 for #64 |
| Reviewed-SHA state fields, authoritative-SHA rule, reviewer ownership beyond what §4 annotates | [#63](https://github.com/amirbena/code-review-skill/issues/63) |
| Change classes, blast-radius attribution mechanics, escalation triggers beyond what §5/§6 reuse | [#64](https://github.com/amirbena/code-review-skill/issues/64) |
| Finding identity, matching, and lifecycle states/events | [#58](https://github.com/amirbena/code-review-skill/issues/58) / [#59](https://github.com/amirbena/code-review-skill/issues/59) / [#60](https://github.com/amirbena/code-review-skill/issues/60) / [#62](https://github.com/amirbena/code-review-skill/issues/62) |
| Building, reordering, or merging a stack; replacing GitHub's own branch management | Explicitly a Non-Goal of #119 |
| Reviewing an entire stack as one combined PR by default | Explicitly a Non-Goal of #119 |
| Base/head fidelity mechanics themselves (resolving a single PR's base/head/merge-base) | [`repository-checkout.md`](../../skills/github-pr-review/policies/repository-checkout.md) |

If work needed for one of those Issues is discovered while building #119,
document the dependency here rather than absorbing it.
