# Policy — Stacked / Dependent PR Review

Installs, as packaged runtime behavior, Issue #119's stacked/dependent-PR
review semantics. This policy is the single normative source for how
`github-pr-review` detects stack topology, derives the effective review
base, scopes the owned delta, persists stack state for re-review, and
renders the detected stack in review output. It reuses, and does not
redefine, the existing base/head fidelity mechanics
([`repository-checkout.md`](repository-checkout.md)), the Reviewed State
Record ([`stateful-delta-rereview.md`](stateful-delta-rereview.md), §1),
the delta re-review change classes and escalation triggers
([`stateful-delta-rereview.md`](stateful-delta-rereview.md)), and the
shared Review Target / Repository Context distinction
([`review-context.md`](../../../shared/policies/review-context.md)) and
one-owner-per-scope invariant
([`review-ownership.md`](../../../shared/policies/review-ownership.md)).
Section references below (`§n`) are to this file's own sections unless
stated otherwise.

Canonical index: [`github-review.md`](github-review.md). Runs after
[`stateful-delta-rereview.md`](stateful-delta-rereview.md) has resolved
eligibility for reconciling prior finding/lifecycle state, and before
[`pr-scope.md`](pr-scope.md) retrieves PR scope and
[`repository-checkout.md`](repository-checkout.md) establishes base/head
fidelity for the checkout — because both of those need to operate against
the **effective review base** this policy resolves, not the repository's
default/target branch, whenever the PR is a stack layer.

```text
stateful-delta-rereview.md resolves reconciliation eligibility
        ↓
this policy: resolve stack topology and effective review base
   ├─ base ref is the repository's default/target branch
   │    → not a stacked layer; every rule below is a no-op; proceed exactly
   │      as before this policy existed
   └─ base ref is another branch
        → determine whether it is itself an open PR's head; walk the
          chain to the root, or fail safe per §4 (never silently narrow
          scope)
        ↓
pr-scope.md / repository-checkout.md use the effective base, not the root,
for scope retrieval and base/head fidelity
        ↓
review-output.md renders the detected stack and active layer (§7)
```

## 1. Terminology

- **Stack** — an ordered chain of branches/PRs where each PR's declared
  base ref is another PR's branch, terminating at the repository's
  default/target branch (the **root**): `root -> PR A -> PR B -> PR C`.
- **Layer** — one PR in the stack; layer `N` is the `N`-th PR counted from
  the root.
- **Effective review base** of the layer under review — that PR's own
  declared base ref, resolved to its SHA at review time. When the
  declared base is another PR's branch, the effective review base is that
  PR's **current head** — never the root, and never assumed to be the
  root merely because that is the common case.
- **Owned delta** — `merge-base(effective_base_head, layer_head) ..
  layer_head`. Ordinary PR-delta math; the only change from a non-stacked
  review is which SHA is "the base."
- **Inherited delta** — everything already present in the effective review
  base but not in the root (recursively, every lower layer's own owned
  delta). This is **Repository Context**
  ([`review-context.md`](../../../shared/policies/review-context.md)),
  never an additional Review Target.
- **Root** — the repository's actual default/target branch. A PR whose
  declared base already is the root is layer 1 of a one-layer "stack" —
  an ordinary, non-stacked review, and every existing rule in
  [`repository-checkout.md`](repository-checkout.md) and
  [`stateful-delta-rereview.md`](stateful-delta-rereview.md) applies
  completely unchanged. Detecting this case is the very first check below
  and, for the overwhelming majority of PRs, the only one that fires.

## 2. Detecting a stack and resolving the effective base

1. Resolve the PR's declared base ref and SHA exactly as
   [`repository-checkout.md`](repository-checkout.md), "Base / head
   fidelity," already requires — never assume the repository's
   default/target branch equals the declared base.
2. **If the declared base *is* the repository's default/target branch**,
   this PR is an ordinary, non-stacked review. Stop here: no further
   chain-walking happens, no stack is reported beyond "none detected," and
   nothing else in this policy changes any existing behavior for this PR.
   This is the byte-for-byte-unchanged path every non-stacked PR takes.
3. **Otherwise**, the declared base is a stack layer's immediate parent.
   Using the same authenticated GitHub integration already used for PR
   metadata ([`github-review.md`](github-review.md), "GitHub integration
   contract"), determine whether that base branch corresponds to another
   **open** PR against this repository (e.g. listing open PRs whose head
   ref matches the base branch name):
   - **If it does**, that PR is the immediate parent layer. Recurse from
     step 1 using that PR's own declared base, building the chain upward
     until step 2 stops it at the root, a further parent is not found (see
     the next bullet), or resolution fails (§4).
   - **If it does not** (an unreviewed shared integration branch, or the
     parent PR was already merged/closed — see §4, "Closed or merged
     lower PR"), treat that base branch itself as the effective review
     base for this layer, without assuming it is or is not itself a stack
     layer; do not walk its further ancestry unless a further open PR is
     found for it.
4. The **effective review base** for the layer under review is the
   immediate parent's **current head SHA** — never a guess, never the
   root, never "whatever the default branch happens to point at right
   now."
5. Introduce no new Git mechanics: `pr-scope.md`'s scope retrieval and
   `repository-checkout.md`'s base/head fidelity ("Base advanced after the
   branch was cut") apply exactly as before, against the effective review
   base resolved here instead of the root.

Record, for later re-review (§5): the effective-base identity (root, or
the parent PR's number/identity) and its head SHA at this review time —
see §6.

## 3. Owned vs. inherited delta

Because the owned delta (§1) is computed against the effective review
base (§2), not the root, ordinary PR-delta math already yields the
correct scope. No separate filtering step is needed to avoid duplicate
findings, inflated scope, or wrong attribution.

- **Owned delta is the Review Target.** Every finding this layer's review
  reports must be causally connected to it, exactly as
  [`repository-checkout.md`](repository-checkout.md), "Repository Context
  must not widen the Review Target," already requires.
- **Inherited delta is Repository Context.** It may be read to understand
  interfaces, invariants, and surrounding behavior the owned delta
  interacts with, but a defect whose only causal site is inside the
  inherited delta, with no attributable connection to the owned delta, is
  **not** a finding this layer's review reports. It belongs to whichever
  layer actually owns that code.
- **Blast radius still applies across the layer boundary.** If the owned
  delta causally interacts with inherited code (calls a function a lower
  layer introduced, changes a shared type a lower layer also touches),
  that interaction is evaluated with the same evidence-based blast-radius
  rule [`stateful-delta-rereview.md`](stateful-delta-rereview.md), §4,
  already applies to any other code the owned delta touches. The
  owned/inherited boundary changes *whose* code a defect's root cause sits
  in; it never changes whether an evidenced, delta-attributable defect
  gets reported.

## 4. Safe failure for ambiguous or broken topology

**Guiding principle:** when the stack topology, or a layer's relationship
to it, cannot be resolved safely, fail closed to a **wider**, never a
narrower, review scope. Under-scoping can silently hide a real defect;
over-scoping only costs redundant effort. Two fallback tiers, narrowest to
widest:

### Tier 1 — single-hop fallback

Applies when the chain **beyond the immediate parent** cannot be resolved
cleanly, but the PR's own declared base ref/SHA is still trustworthy: the
merge-base between the effective base and the current head cannot be
resolved to a single unambiguous commit (criss-cross or octopus merge on
the boundary), or it cannot be determined with confidence whether the
immediate base branch corresponds to a further open PR.

**Fallback:** review this layer as an ordinary, single-hop PR review
against its own currently declared base ref/SHA (§2), exactly as if no
deeper stack were being detected. This is always safe — the owned delta
computed this way is the same PR-delta math every non-stacked review
already trusts — and only forgoes the *display* of further stack layers
below it.

### Tier 2 — root fallback

Applies when even the single-hop relationship cannot be trusted:

- **Rebase / force-push on the current layer itself** — the prior
  reviewed state (if any) is invalidated per
  [`stateful-delta-rereview.md`](stateful-delta-rereview.md); perform a
  fresh full review of the new head.
- **Changed parent branch (retarget)** — the PR's declared base ref itself
  changed. Any reviewed state recorded against the old base is
  invalidated; the newly declared base is re-derived from current state
  (§2) as the effective base for a fresh review — neither the old nor the
  new base is assumed "correct."
- **Closed or merged lower PR:**
  - An ordinary (non-squash, non-rebase) or fast-forward merge leaves the
    lower layer's original commits, unchanged, as ancestors of the root.
    Re-deriving the effective base per §2 naturally resolves to the root
    once the lower layer's branch no longer corresponds to an open PR and
    is fully merged. No fallback is needed.
  - A **squash or rebase merge** of the lower layer (whichever merge
    strategy the *reviewed* repository actually used for it) leaves the
    lower layer's original commits absent from the root, so a naive
    `merge-base(root, layer_head)` would resolve to a point before the
    lower layer even started, making all of its changes appear to be part
    of this layer's diff. **Fallback:** full review of this layer's
    current head against the root, with the stack display (§7) explicitly
    reporting the topology as unresolved/desynced and recommending the
    layer be rebased onto the root before stacked review is reliable
    again.
- **Cycle or otherwise malformed chain** (base refs resolve circularly, or
  the chain cannot be walked to the root within a reasonable bound) —
  nonsensical topology, not an edge case. **Fallback:** full review of the
  current head against the root, with the stack explicitly reported as
  "topology undetermined." No arbitrary point in the cycle is picked as
  the effective base.

In every Tier 2 case, "full review against the root" may review some
content a correctly resolved stack would have excluded as inherited. That
is the accepted, safe-direction cost: it never silently drops a defect,
and it never fabricates an owned/inherited split the topology does not
actually support.

## 5. A lower PR changes after an upper PR was reviewed

**Trigger condition.** The effective-base SHA recorded for this layer's
last review (§2/§6) no longer matches the immediate parent's **current**
head SHA. This is the stack-layer instance of an ordinary "base branch
advanced" case; only the fact that "the base" is another PR, not the
root, is new. Resolve it exactly as
[`stateful-delta-rereview.md`](stateful-delta-rereview.md)'s existing
change-class/escalation model, applied one layer up:

| Condition on the parent's new commits (relative to this layer's recorded effective-base SHA) | Effect on this layer's re-review |
|---|---|
| The recorded head SHA is still an ancestor of the parent's new head (ordinary forward progress, no rebase), **and** the new commits have no [`stateful-delta-rereview.md`](stateful-delta-rereview.md) §4 blast-radius attribution into this layer's owned delta | **No re-review required.** This layer's Reviewed State Record for its own owned delta stays valid; only the inherited-context view is stale and is refreshed (re-read, not re-reviewed) at the next review for any other reason. |
| Same ancestry condition, **but** the new commits are §4-attributable into this layer's owned delta (a shared interface, type, or config the owned delta depends on changed underneath it) | **Partial (bounded delta) re-review**, scoped to the blast-radius interaction — an ordinary delta re-review trigger, applied across the layer boundary exactly as it would apply to any other code the owned delta causally touches. |
| The recorded head SHA is **no longer an ancestor** of the parent's new head (rebase, force-push, or history rewrite on the lower layer) | **Escalate to a full review** of this layer. An unreachable/non-ancestor prior SHA invalidates the assumptions this layer's earlier review made about what it had already accounted for as inherited; a bounded delta cannot safely reconstruct that. |

No numeric threshold is introduced — the trigger is evidence-based
(ancestry check, blast-radius attribution), matching
[`stateful-delta-rereview.md`](stateful-delta-rereview.md)'s own refusal
to invent one. This table is an **additional** trigger this policy
contributes to that file's §6 "Escalation to a broader/full review" list
— it does not replace any of that file's own triggers, and that file's own
escalation triggers (prior assumptions invalidated, unbounded blast
radius, broadly unreliable matching, violated reviewed-state
preconditions) apply to a stack layer exactly as to any other PR.

## 6. Persisted state for reliable re-review

This policy introduces **no** second, parallel state record. A stack
layer's Reviewed State Record is the same record
[`stateful-delta-rereview.md`](stateful-delta-rereview.md), §1, already
reconstructs from GitHub-native evidence, carrying one additional,
stacking-specific annotation on its existing base-branch-name field:

- **Base branch name** (unchanged) — for a stack layer, this is the
  immediate parent's branch name (e.g. `feature/pr-a`), not the root.
- **Base SHA at review time** (unchanged) — for a stack layer, this is
  the immediate parent's head SHA at review time (§2), not the root's
  tip. Comparing this recorded value against the parent's **current**
  head SHA is exactly the §5 trigger check.
- **Merge-base SHA at review time** (unchanged) — computed between the
  effective review base and the reviewed head, as usual.
- **Effective-base provenance (new annotation, not a new field)** — whether
  the effective review base is the repository's default/target branch
  (root) or another open PR, and, when it is another open PR, that PR's
  identity (number/URL). This lets a later re-review distinguish "the base
  is the root and moved" (ordinary base-movement handling, unchanged) from
  "the base is another PR and *that PR* may have changed, been retargeted,
  or been merged/closed" (§4/§5 above, which need topology-aware checks a
  simple branch-tip comparison cannot make).

No other new field is required. The reviewed head SHA, reviewer identity,
review result, completeness, prior reviewed SHA, and optional evidence
reference are populated exactly as
[`stateful-delta-rereview.md`](stateful-delta-rereview.md), §1, already
specifies.

## 7. Review output

The review output states, for the layer under review:

- **the detected stack**, root to current layer (e.g.
  `main -> PR A -> PR B -> PR C`), or an explicit "no deeper stack
  detected" / "topology fell back: `<tier>`, `<reason>`" statement;
- **which layer is currently under review** (e.g. "reviewing layer 3 of
  3: PR C");
- **the effective review base actually used** (branch/PR identity and
  SHA), distinct from the repository's default/target branch when they
  differ;
- when a Tier 1 or Tier 2 fallback (§4) applied, **which one and why**, so
  a human reviewer understands the scope was widened, never silently
  narrowed.

Concrete rendering — the subordinate-metadata field, and the one-sentence
opening note when a stack is detected — is owned by
[`review-output.md`](review-output.md), "Stacked-PR context," and
[`../templates/external-review-summary.md`](../templates/external-review-summary.md),
"Stacked-PR context." A non-stacked PR (§2 step 2) renders the same "no
stack detected" value it always would, so this requirement adds no
visible change to the output of the overwhelming majority of reviews.

## 8. Non-stacked PRs are provably unaffected

For a PR whose declared base is the repository's actual default/target
branch, §2 step 2 is the entire effect of this policy: detect that fact
and stop. Every downstream decision — scope retrieval, base/head fidelity,
delta re-review eligibility and reconciliation, findings, severity,
placement, and the final decision — proceeds through exactly the same
policies, in exactly the same order, using exactly the same inputs, as
before this policy existed. This policy defines no new finding, no new
severity rule, and no new decision path for the non-stacked case; the only
observable output difference is the "no stack detected" line in §7, which
is itself a no-op statement of the pre-existing behavior.

## 9. Scope boundaries

This policy governs stack-topology detection, effective-base derivation,
owned/inherited delta scoping, safe failure, the lower-layer re-review
trigger, the one persisted-state annotation, and output rendering for
`github-pr-review` only. It explicitly does **not** define, and must not
be read as redefining:

| Not defined here | Owner |
|---|---|
| Base/head fidelity mechanics themselves (resolving a single PR's base/head/merge-base) | [`repository-checkout.md`](repository-checkout.md) |
| Reviewed-SHA state fields, authoritative-SHA rule, reviewer ownership beyond the one annotation §6 adds | [`stateful-delta-rereview.md`](stateful-delta-rereview.md), §1 |
| Change classes, blast-radius attribution mechanics, and escalation triggers this policy reuses | [`stateful-delta-rereview.md`](stateful-delta-rereview.md) |
| Finding identity, matching, and lifecycle states/events | [`pr-scope.md`](pr-scope.md), [`stateful-delta-rereview.md`](stateful-delta-rereview.md) |
| Review Target / Repository Context / Existing Review Evidence concepts | [`review-context.md`](../../../shared/policies/review-context.md) |
| One review scope → one owner | [`review-ownership.md`](../../../shared/policies/review-ownership.md) |
| Building, reordering, or merging a stack; replacing GitHub's own branch management | Explicitly a non-goal — not built by this policy |
| Reviewing an entire stack as one combined PR by default | Explicitly a non-goal — not built by this policy |

`local-code-review` does not load this policy: stack topology is a
GitHub-PR-specific concept (declared base refs between open PRs) with no
analogue in a local, not-yet-PR'd delta.
