# Reviewed-SHA State — Contract

Repository-development doc. It defines the **canonical reviewed-SHA state
model**: what repository/review state must exist to say

> *this commit SHA was reviewed, under this review context, by this
> reviewer, and can be used as the prior reviewed state for a future
> re-review.*

It fixes that contract so the follow-on stateful-re-review work can be
built against it instead of rediscovering it:

- review delta / re-review semantics — GitHub Issue
  [#64](https://github.com/amirbena/code-review-skill/issues/64);
- implementing re-review state handling — GitHub Issue
  [#65](https://github.com/amirbena/code-review-skill/issues/65);
- re-review regression fixtures — GitHub Issue
  [#66](https://github.com/amirbena/code-review-skill/issues/66);
- finding lifecycle states — GitHub Issue
  [#62](https://github.com/amirbena/code-review-skill/issues/62);
- parent capability — GitHub Issue
  [#43](https://github.com/amirbena/code-review-skill/issues/43).

This file is **contract / requirements only**. It does **not** implement
state loading, compute a delta, define finding lifecycle states, or match
findings across revisions. Wherever a section below stops at "enough state
for a downstream pass to decide," **that decision is the named Issue's**,
not this document's.

This is a repository-development doc, like
[`finding-identity-requirements.md`](finding-identity-requirements.md) and
[`../runtime-parallelism.md`](../runtime-parallelism.md): it is **not** packaged
into either Skill archive, and no packaged Skill resource depends on it.
Its standing relative to the eventual runtime policy is defined in
"Status and canonical home" at the end.

The review-target / review-context / repository-context / existing-review-
evidence vocabulary is
[`../../shared/policies/review-context.md`](../../shared/policies/review-context.md)
and
[`../../shared/policies/review-evidence.md`](../../shared/policies/review-evidence.md).
The reviewer-ownership and delta-boundary rules this contract aligns with
are
[`../../shared/policies/review-ownership.md`](../../shared/policies/review-ownership.md),
[`../../skills/github-pr-review/policies/reviewer-delta-review.md`](../../skills/github-pr-review/policies/reviewer-delta-review.md),
[`../../skills/github-pr-review/policies/review-status-enforcement.md`](../../skills/github-pr-review/policies/review-status-enforcement.md),
and
[`../../skills/local-code-review/policies/repository-state.md`](../../skills/local-code-review/policies/repository-state.md).

---

## Summary

Each point is stated normatively in the section named; this list only
orients.

- **The reviewed SHA is a recorded fact, never the current tip** (§1, §2).
  A branch moving does not make its new HEAD "reviewed"; only a completed
  review that writes a new record does.
- **Minimal but sufficient record** (§1). Repository identity, review base
  (name + SHA), merge-base, reviewed head SHA, reviewer identity, review
  result, full-vs-delta, prior reviewed SHA (whenever a same-reviewer
  predecessor was superseded — `full` records included), a
  provenance/timestamp marker, and an *optional* opaque reference to that
  review's findings.
- **Authoritative SHA = the recorded reviewed head SHA** (§2). Added
  commits, moved refs, a changed PR head, an advanced base, a rebase, or a
  force-push never silently update it.
- **Base context is recorded, not re-derived** (§3). The record stores the
  base branch name, the base SHA at review time, and the merge-base, so a
  later pass can *detect* base movement without guessing — it does not
  define how to fold that movement in.
- **Reviewed state is reviewer-owned and non-transferable** (§4). A
  different reviewer, or an unverifiable reviewer identity, gets a fresh
  full review; the record is still visible as Existing Review Evidence.
- **The supersession chain is explicit** (§5). `review completeness` and
  `prior reviewed SHA` are independent: any record — `full` or
  `delta-re-review` — names at most one prior reviewed SHA, the
  same-reviewer state it superseded. The chain root is the review with no
  established same-reviewer predecessor, not necessarily every `full`
  review. No recursion, no guessing which SHA a review superseded.
- **Trust is tiered** (§6): authoritative, user-supplied, inferred,
  unavailable/ambiguous. Inferred state never seeds a delta. No new
  persistence service is introduced.
- **Unsafe or ambiguous prior state falls back to a fresh full review**
  (§7), never a silently constructed delta.
- **Finding identity/matching/lifecycle is out of scope** (§8). The record
  may hold an opaque *reference* to the prior findings; it never embeds a
  findings payload and never defines how findings are identified or
  matched.

---

## 1. What a reviewed SHA is

A **reviewed SHA** is not a bare commit hash. It is the reviewed head SHA
*inside a Reviewed State Record* — the minimum state that lets a later
review treat a commit as an established, reusable prior reviewed state.

A commit SHA is "reviewed" only when a **completed review** produced a
record binding it to the context it was reviewed under. A commit that a
branch happens to point at, or that was pushed after the last review, is
**not reviewed** — see §2.

### The Reviewed State Record

Every field below is present *because a downstream Issue needs it*, not
because it may be useful. All are required to establish trustworthy
reviewed-SHA state **except the last** — *Associated review evidence
reference* is optional/recommended. A record missing a required field is
incomplete and cannot seed a delta re-review (§7); a record missing only
the optional reference is still valid reviewed state (§7, §8).

| Field | What it holds | Why it is in the record |
|---|---|---|
| **Repository identity** | The canonical repository the review ran against (remote/owner/repo identity for a PR; the local repository identity for local review). | Reviewed state is single-repository only. A record from a different repository identity is never a delta seed (§7), matching the single-repository scope in [`finding-identity-requirements.md`](finding-identity-requirements.md), §8. |
| **Base branch name** | The base/target branch the change was reviewed against (e.g. `main`). | Lets a later pass resolve "the same base" and detect a base **reassignment** (§3). A SHA alone cannot. |
| **Base SHA at review time** | The exact commit the base branch pointed at when the review ran. | Lets [#64](https://github.com/amirbena/code-review-skill/issues/64) tell whether the base **moved** since the review (§3, Example C). |
| **Merge-base SHA at review time** | `merge-base(base, head)` as computed for the review. | The lower bound of the range the review actually covered (`merge-base..reviewed head`). Recorded so a later pass has the *observed* value instead of re-deriving it; **how** a re-review uses it is [#64](https://github.com/amirbena/code-review-skill/issues/64)'s to define (§3). |
| **Reviewed head SHA** | The exact commit that was reviewed. | The spine of the record and the authoritative reviewed SHA (§2). |
| **Reviewer identity** | The identity that owns this reviewed state — the authenticated GitHub identity for a PR review; the established local review ownership context for local review. | Delta re-review is reviewer-owned (§4). A record whose reviewer cannot be established is not a delta seed. |
| **Review result** | The verdict the review produced: `REVIEW CLEAN` / `CHANGES REQUIRED` (local), `Approve` / `Request Changes` / `recommendation-only` (PR), or an explicit non-graded outcome (`REVIEW INCOMPLETE`, `JIRA CONTEXT UNRESOLVED`, `NO NEW DELTA`). | Only a **completed, graded** review is a valid prior state to diff from. A non-graded outcome is recorded but never seeds a delta (§7). |
| **Review completeness** | `full` or `delta-re-review` — how much of the current state *this* review covered. Independent of **Prior reviewed SHA** below (§5). | Lets a later pass tell whether the recorded review already covered the whole current state or only a bounded delta. |
| **Prior reviewed SHA** | The reviewed head SHA of the established prior same-reviewer reviewed state this review **superseded**, if any. Recorded whenever such a predecessor exists — **including when this review is `full`** (e.g. a delta re-review that escalated to full). Absent only when there is no established same-reviewer predecessor (the chain root). | Lets [#64](https://github.com/amirbena/code-review-skill/issues/64) / [#65](https://github.com/amirbena/code-review-skill/issues/65) reconstruct the supersession chain (`full → delta → delta`, `full → delta → escalated-full → delta`) without guessing which SHA each review superseded (§5). |
| **Provenance marker** | When the record was produced and by which mechanism (submitted GitHub review, published SHA-bound status, carried-forward local report, explicit user input). | Drives the trust tiering in §6 and the selection of the "immediately preceding" review. |
| **Associated review evidence reference** | *Optional (recommended).* An **opaque reference / association** to the findings (and any recorded per-finding state) that review produced. Storage-neutral: the record points at that evidence, it does not have to embed it. | When present, lets [#64](https://github.com/amirbena/code-review-skill/issues/64) / [#65](https://github.com/amirbena/code-review-skill/issues/65) reconcile findings across revisions. When absent, a **commit-range** re-review is still possible — only finding-level reconciliation is limited (§7). This document does **not** interpret the evidence — see §8. |

Fields deliberately **not** in the record: the current branch tip, "commits
since task start," a branch-name convention, any cross-repository pointer,
any finding-identity or finding-matching structure, any lifecycle-state
machine, any embedded findings payload or serialization format (a reference
is enough — see **Associated review evidence reference** above). Adding
those is another Issue's concern, not this contract's.

### Local review is stateless; the "record" is the carried-forward report

`local-code-review` does not persist anything itself — it computes and
reports the current repository-state categories and the staged-delta
fingerprint every invocation and remembers nothing between invocations
([`../../skills/local-code-review/policies/repository-state.md`](../../skills/local-code-review/policies/repository-state.md),
"This Skill remains stateless"). For local review, the Reviewed State
Record **is** the prior review's reported output as carried forward by the
orchestrator/caller — the reviewed base, the reviewed committed/staged
delta, the staged-delta fingerprint, the verdict, and the prior findings.
The fields in the table above are populated from that report, not from a
store. This is a real asymmetry with GitHub PR review (§6) and is called
out so downstream work does not assume a local persistence layer exists.

---

## 2. Which SHA is authoritative

**The authoritative reviewed state is the reviewed head SHA recorded in
the Reviewed State Record — never the current branch tip, the latest
commit, the last push, or a SHA inferred from a ref name.** This mirrors
[`../../skills/github-pr-review/policies/reviewer-delta-review.md`](../../skills/github-pr-review/policies/reviewer-delta-review.md),
"Same reviewer: delta boundary and scope" ("Never define this boundary
merely as the latest commit, the last push, the last local commit, or
'commits since task start'").

| Situation | Authoritative reviewed SHA | Is the prior state usable as a delta seed? |
|---|---|---|
| Working tree clean, no new commits since the review | the recorded reviewed head SHA (call it `B`) | Yes. If the current review head also equals `B` and the review standard is unchanged, this is `NO NEW DELTA` — no new review is manufactured (see [`../../skills/github-pr-review/policies/review-output.md`](../../skills/github-pr-review/policies/review-output.md), "Final decision," and the staged-fingerprint short-circuit in [`../../skills/local-code-review/policies/repository-state.md`](../../skills/local-code-review/policies/repository-state.md)). |
| Commits added after the review; branch now at `C` | still `B` | Yes — `B` is the prior reviewed state; the new delta is `B..C`. `C` is **not** reviewed until a new review completes and writes a new record. |
| Remote branch ref moved | still `B` (the record binds a SHA, not a ref) | Yes — a moved ref is only a trigger to re-review; it never rewrites the reviewed SHA. |
| PR head changed | still `B` | The new head must be re-reviewed. An old review/record/approval never covers the new head — consistent with HEAD revalidation ([`../../skills/github-pr-review/policies/review-output.md`](../../skills/github-pr-review/policies/review-output.md)) and "a new SHA inherits no green" ([`../../skills/github-pr-review/policies/review-status-enforcement.md`](../../skills/github-pr-review/policies/review-status-enforcement.md)). |
| Base branch advanced (`main` moved), head unchanged at `B` | still `B`; `B` remains genuinely reviewed **as of the recorded base** | Yes for the head; the **base context** is now stale (recorded base SHA / merge-base no longer match). The record carries enough (§3) for [#64](https://github.com/amirbena/code-review-skill/issues/64) to detect this and decide whether the delta must widen. No assumption that the review still covers interactions with new base commits. |
| Branch rebased | typically **none** — `B` is usually no longer an ancestor of (or present in) the rewritten history | No. If the recorded reviewed head SHA is missing from the repository, or is not an ancestor of the current review head, the prior state cannot seed a delta — fall back to a full review (§7, Example D). |
| Branch force-pushed | same as rebase — depends on whether `B` is still reachable and an ancestor | No when `B` is unreachable or not an ancestor. This is the invalidation Issue [#63](https://github.com/amirbena/code-review-skill/issues/63) explicitly calls for. |

### The usability rule

Prior reviewed state remains usable **as a delta base** only when **all**
of the following hold:

1. the recorded reviewed head SHA still exists in the repository **and** is
   an ancestor of the current review head;
2. the recorded repository identity matches the current one;
3. reviewer ownership is verified on both sides (§4);
4. the base context is either unchanged, or its change is fully described
   by the recorded fields so a downstream pass can reconcile it (§3).

If any condition fails, the prior state is not a safe delta base →
**fresh full review** (§7). The record may still be read as Existing
Review Evidence
([`../../shared/policies/review-evidence.md`](../../shared/policies/review-evidence.md))
— that is a separate, weaker use than seeding a delta.

---

## 3. Relationship to the base branch

The Reviewed State Record stores **all three** of: the **base branch
name**, the **base SHA at review time**, and the **merge-base SHA at
review time**. None alone is sufficient:

- **base branch name** — so a re-review can resolve "the same base" later
  and detect that the PR's base was **reassigned** to a different branch;
- **base SHA at review time** — so a re-review can tell whether the base
  **moved at all** since the review;
- **merge-base SHA at review time** — the observed lower bound of the
  range the previous review actually covered (`merge-base..reviewed
  head`). It is recorded so [#64](https://github.com/amirbena/code-review-skill/issues/64)
  works from the value seen at review time rather than re-deriving it
  against moved history. This contract does **not** say how a re-review's
  delta uses it.

### What downstream may infer without guessing

From a valid record, [#64](https://github.com/amirbena/code-review-skill/issues/64)
can establish, purely from stored state:

- the commit range the previous review covered: `recorded merge-base .. recorded reviewed head`;
- whether the base branch moved: `current base SHA` vs. `recorded base SHA`;
- whether the base branch itself was changed: `current base name` vs. `recorded base name`;
- whether the reviewed head is still an ancestor of the current head, and
  the recorded prior reviewed SHA (§5) for the previous review.

This document defines only that the state above is **recorded**. **How** a
re-review turns it into a delta — which commit range it re-reviews,
whether new base commits are in scope, how the merge-base is recomputed,
which prior findings are re-surfaced — is
[#64](https://github.com/amirbena/code-review-skill/issues/64)'s to
define. See Example C.

---

## 4. Reviewer ownership

Reviewed-SHA state is **reviewer-specific**, aligned with
[`../../skills/github-pr-review/policies/reviewer-delta-review.md`](../../skills/github-pr-review/policies/reviewer-delta-review.md)
and the single-owner invariant in
[`../../shared/policies/review-ownership.md`](../../shared/policies/review-ownership.md).

- **Reviewer-specific.** The record's reviewer identity is part of what
  makes it usable as a delta seed. A delta re-review is only valid when
  the current reviewer is the same identity as the record's reviewer.
- **Not transferable.** A different reviewer does **not** inherit another
  reviewer's reviewed state as a delta base. They perform a normal full
  review of the current state. They still see the prior record as Existing
  Review Evidence — reconciled, not inherited
  ([`../../shared/policies/review-evidence.md`](../../shared/policies/review-evidence.md)).
- **Reusable only when reviewer identity is reliably established** on
  **both** sides — the current reviewer and the record's reviewer. Use the
  strongest repository/GitHub evidence available (authenticated identity;
  the reviewer recorded on the immediately preceding *submitted* review).
  Never infer reviewer ownership from task wording, branch name, commit
  author, or the mere existence of a prior review — verbatim with the
  existing "Reviewer identity" rule.
- **Prior reviewer identity cannot be established** (unresolvable account,
  ambiguous mapping, more than one plausible "immediately preceding"
  review) → the record is **not** a valid delta seed → fall back to a
  normal full review. Its other contents may still inform the review as
  evidence, but they cannot bound a delta.

A self-review (current reviewer is the PR author) does not change any of
this: reviewed-state ownership and delta-mode selection work the same for
a self-review as for an external one. Whether a self-review may *submit* a
formal GitHub event is a separate concern owned by
[`../../skills/github-pr-review/policies/review-action-authorization.md`](../../skills/github-pr-review/policies/review-action-authorization.md).

---

## 5. Full review vs. re-review

Two **independent** properties, not one:

- **`review completeness ∈ {full, delta-re-review}`** — how much of the
  *current* state this review covered: the whole thing (`full`) or a
  bounded delta (`delta-re-review`).
- **`prior reviewed SHA`** — the reviewed head SHA of the established
  same-reviewer reviewed state (§4) this review **superseded**, recorded
  whenever such a predecessor exists and absent only at the chain root.

These do not track each other. A re-review that begins delta-only but
**escalates to a full review of the current state** (per
[`../../skills/github-pr-review/policies/reviewer-delta-review.md`](../../skills/github-pr-review/policies/reviewer-delta-review.md),
"Escalating from delta to full review") completes as `full` **and** still
records the same-reviewer predecessor it superseded. This contract only
makes the state model able to represent that outcome; it does not define
the escalation decision itself — that is
[`reviewer-delta-review.md`](../../skills/github-pr-review/policies/reviewer-delta-review.md)'s.

### Reconstructing the chain

Follow `prior reviewed SHA` links backward. Both shapes reconstruct
without guessing:

```text
full → delta → delta

record₃  reviewed head = C   completeness = delta-re-review   prior reviewed SHA = B
   ↓
record₂  reviewed head = B   completeness = delta-re-review   prior reviewed SHA = A
   ↓
record₁  reviewed head = A   completeness = full              prior reviewed SHA = ∅  (chain root)
```

```text
full → delta → escalated-full → delta

record₄  reviewed head = D   completeness = delta-re-review   prior reviewed SHA = C
   ↓
record₃  reviewed head = C   completeness = full              prior reviewed SHA = B   (escalated: full, but has a predecessor)
   ↓
record₂  reviewed head = B   completeness = delta-re-review   prior reviewed SHA = A
   ↓
record₁  reviewed head = A   completeness = full              prior reviewed SHA = ∅  (chain root)
```

This is unambiguous and non-recursive:

- each record names **at most one** prior reviewed SHA — the same-reviewer
  state it superseded — regardless of its own `completeness`;
- the chain **root** is the record with **no established same-reviewer
  predecessor** (`prior reviewed SHA = ∅`). A `full` record is the root
  only when it also has no predecessor; a `full` record that superseded an
  earlier same-reviewer review is **not** the root;
- a record must **not** name itself as its prior;
- `prior reviewed SHA` must be an ancestor of that record's own reviewed
  head SHA (a re-review moves history forward, never backward).

If any of these do not hold, the chain is **broken**: a downstream
implementation treats the prior state as unusable and falls back to a full
review (§7) rather than guessing which SHA a review superseded.

What each change class (`fixed` / `unchanged` / `moved` / `reopened` /
`newly introduced`) means, and which prior findings re-surface, is
[#64](https://github.com/amirbena/code-review-skill/issues/64)'s to
define — this section only guarantees the chain can be reconstructed.

---

## 6. Persistence / provenance

A trustworthy source of reviewed-SHA state is one the review workflow can
**re-read** and that binds a **specific SHA** to a **specific reviewer**.
This contract introduces **no new persistence service** — it rides on
mechanisms that already exist.

### Trust tiers

1. **Authoritative / trusted state** — produced by a completed review
   through a mechanism the review workflow itself controls:
   - **GitHub PR review**: the reviewed HEAD SHA recorded on a
     **submitted** GitHub review by the same authenticated reviewer
     (retrieved per
     [`../../skills/github-pr-review/policies/pr-scope.md`](../../skills/github-pr-review/policies/pr-scope.md),
     "Retrieving prior review activity"; reviewer identity per
     [`../../skills/github-pr-review/policies/reviewer-delta-review.md`](../../skills/github-pr-review/policies/reviewer-delta-review.md)),
     together with this Skill's own published review body and the optional
     exact-HEAD machine-readable status, which is already SHA-bound
     ([`../../skills/github-pr-review/policies/review-status-enforcement.md`](../../skills/github-pr-review/policies/review-status-enforcement.md)).
   - **Local review**: the prior review's **reported output** carried
     forward by the orchestrator — the local review report, its recorded
     repository-state categories, and its staged-delta fingerprint
     ([`../../skills/local-code-review/policies/repository-state.md`](../../skills/local-code-review/policies/repository-state.md)).
     There is no on-disk store; the report *is* the record.
2. **User-supplied state** — a prior reviewed SHA / prior review base the
   caller passes in explicitly. Usable, but **only after validation**: the
   SHA exists, is an ancestor of the current head, and the repository
   identity, reviewer identity, and base context are compatible. Any
   validation failure → full review (§7). Never trusted blindly.
3. **Inferred state** — anything derived indirectly: "the last commit
   before today," a branch-name convention, a timestamp guess, "the latest
   prior review regardless of author," "HEAD minus N." **Not** a
   trustworthy source, and **never** a delta seed — consistent with the
   existing prohibition on defining the delta boundary as the latest
   commit / last push.
4. **Unavailable / ambiguous state** — nothing retrievable, retrieval
   incomplete where completeness matters, or multiple plausible prior
   records. → full review (§7).

### Reporting

The mode actually used is stated concisely in the human-facing review, as
the existing templates already do (`Review mode: Full review` /
`Review mode: Delta re-review` with the previous reviewed SHA and current
HEAD) — see
[`../../skills/github-pr-review/policies/reviewer-delta-review.md`](../../skills/github-pr-review/policies/reviewer-delta-review.md),
"Reporting the mode." Internal identity/matching machinery is not primary
output.

---

## 7. Invalid or ambiguous state

**Guiding principle:** *when prior reviewed state cannot be established
safely, fall back to a fresh full review rather than silently constructing
an unsafe delta.*

Every condition below resolves to a **fresh full review of the current
state**:

| Condition | Resolution |
|---|---|
| The previous reviewed SHA no longer exists in the repository | Full review. Record retained as historical evidence only. |
| The previous reviewed SHA exists but is **not an ancestor** of the current review head (rebase, force-push, divergent history) | Full review. `prior..head` is not a meaningful ancestry range. |
| Repository identity differs from the record's | Full review; do not reuse the record's findings as authoritative evidence either. |
| Base context is incompatible (base branch reassigned, or base moved and the record lacks the fields §3 requires to reconcile it) | Full review of the current state; the record's reviewed head may still be noted. |
| Reviewer ownership cannot be verified on either side (§4) | Full review. |
| Multiple plausible prior reviewed SHAs / records (ambiguous "immediately preceding" review) | Full review — ambiguity never unlocks a delta, matching the existing "fail conservative" rule. |
| Stored state is incomplete — missing **reviewed head SHA**, missing **reviewer identity**, missing the **base data** §3 needs, or a broken §5 chain | Full review. |

A **missing *Associated review evidence reference*** (§1) is **not** an
incompleteness condition. Otherwise-trustworthy reviewed-SHA state stays
valid without it; the only consequence is that a later re-review does
finding-level reconciliation with less prior signal (§8) — a
**commit-range** re-review is still available. It is listed here only to
be explicit that its absence, alone, never forces a full review.

The one case where "reviewed SHA equals the current head" is legitimate is
`NO NEW DELTA` — a **valid record** whose reviewed head SHA equals the
current review head under an unchanged review standard. That is an
established record, not a branch that happens to sit at that commit; no
new review is manufactured.

Falling back to a full review is **not** a failure outcome — it is the
safe default, always valid, exactly as a normal full review is the
default whenever delta re-review preconditions are not met.

---

## 8. Interaction with finding identity

[#63](https://github.com/amirbena/code-review-skill/issues/63) is kept
**independent** of
[#58](https://github.com/amirbena/code-review-skill/issues/58) /
[#59](https://github.com/amirbena/code-review-skill/issues/59) /
[#60](https://github.com/amirbena/code-review-skill/issues/60).

- The Reviewed State Record **may hold an opaque reference / association**
  to the prior review's findings and any recorded per-finding state
  (§1, *Associated review evidence reference*), so a later pass has a
  well-defined prior finding set to diff from. The reference is optional
  and storage-neutral — the record points at that evidence, it never has
  to embed a findings payload, and this contract defines no serialization
  for it.
- This document **does not define**, and a reviewed-SHA implementation
  **must not embed**:
  - how a finding acquires a stable identity across revisions —
    [`finding-identity-requirements.md`](finding-identity-requirements.md)
    ([#58](https://github.com/amirbena/code-review-skill/issues/58)) and
    strategy selection
    ([#59](https://github.com/amirbena/code-review-skill/issues/59)) /
    implementation
    ([#60](https://github.com/amirbena/code-review-skill/issues/60));
  - how findings are matched between the prior payload and a re-review's
    findings — [#59](https://github.com/amirbena/code-review-skill/issues/59);
  - what finding lifecycle states exist or how they transition —
    [#62](https://github.com/amirbena/code-review-skill/issues/62);
  - how the review delta is computed or which findings re-surface vs.
    suppress — [#64](https://github.com/amirbena/code-review-skill/issues/64) /
    [#65](https://github.com/amirbena/code-review-skill/issues/65).

The record's only job with respect to findings is to **anchor** them:
"these findings were produced against reviewed head SHA `B`, by reviewer
`R`, relative to base `X` at merge-base `MB`." Everything the anchor is
*for* belongs to the Issues above.

---

## Required examples

Shared setup: reviewer `R`, base branch `main`, repository identity fixed
throughout unless stated.

### A. Normal re-review

1. Commit `A` receives a **full review** by `R` against `main` at
   `main = M0`, `merge-base = MB0`; result `REVIEW CLEAN`. This writes
   `record₁ = { repo, base=main, base_sha=M0, merge_base=MB0,
   reviewed_head=A, reviewer=R, result=CLEAN, completeness=full,
   prior=∅ }`.
2. The branch advances to `B` (new commits on top of `A`; `main`
   unchanged).
3. `R` re-reviews. `record₁` is valid: `A` exists and is an ancestor of
   `B`; repository identity matches; reviewer is `R` on both sides; base
   context unchanged. Delta seed = `A`. The re-review covers `A..B` plus
   enough surrounding context to confirm no regression and that
   `record₁`'s assumptions still hold.
4. The re-review completes and writes `record₂ = { …, base_sha=M0,
   merge_base=MB0, reviewed_head=B, reviewer=R, result=CLEAN,
   completeness=delta-re-review, prior=A }`.

`B` is now the authoritative reviewed SHA.

### B. Additional commit after review

1. `record₂` exists with `reviewed_head=B`.
2. The branch advances to `C`. **No review is run.**
3. The authoritative reviewed state is **still `B`**. `C` is **not**
   reviewed. A query "is `C` reviewed?" answers **no**.
4. For a future re-review by `R`, the prior reviewed state is `B` and the
   new delta is `B..C`. A request to treat `C` as reviewed *because the
   branch moved* is refused — the branch advancing never updates the
   reviewed SHA (§2). `C` becomes reviewed only when a new review
   completes and writes a new record.

### C. Base branch advances

1. `record₂` has `base=main`, `base_sha=M0`, `merge_base=MB0`,
   `reviewed_head=B`.
2. `main` advances from `M0` to `M1`. The PR head is still `B`.
3. **Retained, usable state:** `reviewed_head=B` (still genuinely reviewed
   *as of base `M0`*), `reviewer=R`, the associated review evidence
   reference (if one was recorded), and — crucially — the recorded
   `base_sha=M0` and `merge_base=MB0`.
4. **Must be re-evaluated later, by
   [#64](https://github.com/amirbena/code-review-skill/issues/64), not
   here:** whether the base commits `M0..M1` interact with the PR's change,
   which commit range the re-review covers, and how the merge-base is
   recomputed. [#63](https://github.com/amirbena/code-review-skill/issues/63)
   guarantees only that `M0` and `MB0` were recorded so that movement is
   *detectable* without guessing. This example deliberately does not
   resolve the delta.

### D. Rebase / rewritten history

1. `record₂` has `reviewed_head=B`.
2. The branch is rebased; the new head is `B′` and `B` is no longer an
   ancestor of `B′` (and may be unreachable / garbage-collectable).
3. `record₂` is **no longer a safe delta seed**: `B..B′` is not a
   meaningful ancestry range. Per §2 condition 1 and §7, the prior
   reviewed state is invalidated for delta purposes.
4. Result: a **fresh full review** of `B′`. `record₂` is retained as
   historical evidence — its findings may still inform investigation — but
   it does not bound a delta. A **force-push** that leaves `B` unreachable
   or non-ancestor is the same case.

### E. Reviewer mismatch

1. `record₂` has `reviewed_head=B`, `reviewer=R`.
2. A different reviewer `S` reviews the PR.
3. `S` is not `R`, so `S` does **not** inherit `R`'s reviewed state as a
   delta base (§4). `S` performs a **normal full review** of the current
   head.
4. `R`'s `record₂` is visible to `S` as Existing Review Evidence — prior
   findings and settled decisions, reconciled against the current target,
   not inherited
   ([`../../shared/policies/review-evidence.md`](../../shared/policies/review-evidence.md)).
   When `S`'s review completes it writes `S`'s own record; it does not
   overwrite or claim `R`'s.

### F. Missing or ambiguous state

Any of: this is the first review of the PR/branch; prior review history
cannot be retrieved; the only prior activity is automation/bot comments;
two prior reviews are equally plausible as the "immediately preceding"
one; the retrievable record is missing its reviewed head SHA or its
reviewer identity.

Result in every case: a **fresh full review** of the current state. No
delta is constructed from a guessed or ambiguous prior SHA (§7).

### G. Delta re-review that escalates to a full review

1. `record₂` exists with `reviewed_head=B`, `reviewer=R`,
   `completeness=delta-re-review`, `prior=A`.
2. The branch advances to `C`. `R` re-reviews, starting delta-only from
   `B`, but the delta materially changes the implementation, so `R`
   **escalates to a full review of the current state** (per
   [`../../skills/github-pr-review/policies/reviewer-delta-review.md`](../../skills/github-pr-review/policies/reviewer-delta-review.md),
   "Escalating from delta to full review").
3. The review completes and writes
   `record₃ = { …, reviewed_head=C, reviewer=R, completeness=full,
   prior=B }` — **`full`, yet it records the predecessor `B` it
   superseded.**
4. Later, `R` re-reviews `C..D`, writing
   `record₄ = { …, reviewed_head=D, completeness=delta-re-review,
   prior=C }`. Walking `prior` links —
   `record₄ → record₃ → record₂ → record₁` — reconstructs the full
   `full → delta → escalated-full → delta` chain with no guessing about
   which SHA `record₃` superseded. If `record₃` had dropped `prior=B`
   merely because it was `full`, that link would be lost.

---

## Status and canonical home

Until
[#65](https://github.com/amirbena/code-review-skill/issues/65)
implements stateful re-review, **this document is the contract record**
for reviewed-SHA state.

**Existing canonical contracts are unchanged and remain authoritative for
what they already own.** This document consolidates and names the
reviewed-SHA state model that each of the following already touches one
facet of; it does not restate or override them:

- [`../../skills/github-pr-review/policies/reviewer-delta-review.md`](../../skills/github-pr-review/policies/reviewer-delta-review.md)
  — reviewer identity, selecting the immediately preceding completed
  review, the delta boundary `previously reviewed SHA → current PR HEAD`,
  escalation from delta to full, and the `NO NEW DELTA` outcome;
- [`../../skills/github-pr-review/policies/review-output.md`](../../skills/github-pr-review/policies/review-output.md)
  and
  [`../../skills/github-pr-review/SKILL.md`](../../skills/github-pr-review/SKILL.md)
  — recording the reviewed HEAD SHA and revalidating it immediately before
  the final decision;
- [`../../skills/github-pr-review/policies/review-status-enforcement.md`](../../skills/github-pr-review/policies/review-status-enforcement.md)
  — exact reviewed-HEAD binding and "a new SHA inherits no status and no
  green";
- [`../../skills/local-code-review/policies/repository-state.md`](../../skills/local-code-review/policies/repository-state.md)
  — the repository-state categories, the staged-delta fingerprint, and
  Skill statelessness;
- [`../../shared/policies/review-evidence.md`](../../shared/policies/review-evidence.md)
  and
  [`../../shared/policies/review-ownership.md`](../../shared/policies/review-ownership.md)
  — reconciling prior review evidence against the current target, and one
  Code Review Agent owner per review scope.

Because this is a repository-development doc, **no packaged Skill resource
depends on it** (see [`../../AGENTS.md`](../../AGENTS.md), "Packaged Skills are
independent of repository-level instructions"), and it is not part of
either Skill archive.

Once
[#65](https://github.com/amirbena/code-review-skill/issues/65)
establishes the canonical runtime rule in a packaged resource (a
`shared/policies/` file, or an extension of one of the Skill policies
above — the path is
[#65](https://github.com/amirbena/code-review-skill/issues/65)'s to
choose), **that policy becomes the single normative source.** This
document then becomes a historical contract record: it MUST link to the
canonical policy and MUST NOT keep evolving the same rules independently —
the same lifecycle as
[`finding-identity-requirements.md`](finding-identity-requirements.md).

## Scope boundaries

This document defines **only** the reviewed-SHA state contract above. It
explicitly does **not** define:

| Not defined here | Owner |
|---|---|
| Review delta / re-review semantics — change classes, which prior findings re-surface vs. suppress, how base movement folds into the delta | [#64](https://github.com/amirbena/code-review-skill/issues/64) |
| Loading prior state, applying transitions, emitting per-finding state, the full-review fallback implementation | [#65](https://github.com/amirbena/code-review-skill/issues/65) |
| Re-review regression fixtures and their assertions | [#66](https://github.com/amirbena/code-review-skill/issues/66) |
| Finding lifecycle states (`new` / `open` / `resolved` / `superseded` / `no longer applicable`) and transitions | [#62](https://github.com/amirbena/code-review-skill/issues/62) |
| What makes two findings "the same" across revisions; the matching strategy; stable finding IDs | [#58](https://github.com/amirbena/code-review-skill/issues/58) / [#59](https://github.com/amirbena/code-review-skill/issues/59) / [#60](https://github.com/amirbena/code-review-skill/issues/60) |
| The normalized Review Target / Review Context / Existing Review Evidence **input schema** shapes | [#45](https://github.com/amirbena/code-review-skill/issues/45) and its children ([#74](https://github.com/amirbena/code-review-skill/issues/74)) |
| Binding a review decision to GitHub merge enforcement / status semantics beyond what `review-status-enforcement.md` already owns | [#49](https://github.com/amirbena/code-review-skill/issues/49) |
| Cross-repository or cross-project reviewed state | Out of scope for [#43](https://github.com/amirbena/code-review-skill/issues/43) entirely |

If work needed for one of those Issues is discovered while building
[#63](https://github.com/amirbena/code-review-skill/issues/63), document
the dependency here rather than absorbing it.
