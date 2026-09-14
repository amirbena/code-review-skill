# Policy — Review Action Authorization

Governs the separation between **review analysis** and **GitHub mutation
authority** for `github-pr-review`: the three publication modes, the safe
non-mutating default, the single canonical publication switch, and the
fail-closed rules that apply when reviewer independence or GitHub
permission cannot be established. Canonical index:
[`github-review.md`](github-review.md). Builds on
[`review-authority.md`](review-authority.md) (identity resolution and the
self-review mutation boundary — authorship forbids a formal self-review
event but never blocks analysis) and is enforced at submission time by
[`review-output.md`](review-output.md), "Review-action authorization
gate."

This policy adds a gate. It never replaces review reasoning, the
mechanical severity → decision derivation
([`../../../shared/policies/severity.md`](../../../shared/policies/severity.md)),
HEAD revalidation, stale-review protection, reviewer ownership
([`../../../shared/policies/review-ownership.md`](../../../shared/policies/review-ownership.md)),
delta re-review semantics
([`reviewer-delta-review.md`](reviewer-delta-review.md)), or the mutation
boundary. The review still runs and still produces a verdict; this policy
only decides whether a GitHub review **mutation** (`APPROVE` /
`REQUEST_CHANGES`) may be **submitted** as a result of it.

## History (issue #314)

Before issue #314 this policy described a review-type axis (passive vs.
active PR review) crossed with an independent, secondary "review-action
mode" axis (`recommendation-only` / `block-only` / `explicitly-authorized
auto-action`) that gated `APPROVE` behind an out-of-band "trusted mutation
authorization" channel — a second activation phrase beyond the caller's
own explicit request for an active review. That two-gate shape was
confusing and, worse, meant an explicit request for "active" review with a
clean verdict still did not publish `APPROVE` without a second,
independently-sourced signal. Issue #314 collapses both axes into **one**
canonical switch — the publication mode below — so a caller's explicit
request for active review is, by itself, sufficient authorization to
publish that review's own outcome, subject only to the **existing**
reviewer-independence, GitHub-permission, self-review, severity, and
decision rules (none of which are weakened by this change). See
"Migration from the pre-#314 model" below for exactly what changed.

## Security principles

These are stated here as normative principles and are not weakened by any
downstream rule, flag, prompt, or invocation.

1. **A review verdict is not, by itself, a GitHub event.** `REVIEW CLEAN`
   becomes a submitted `APPROVE` only once analysis is complete, HEAD is
   revalidated, and the publication mode + independence + permission
   checks below all pass — the reasoning result and the act of submitting
   it remain conceptually distinct steps even though, for an explicitly
   requested active review that clears those checks, the second step is
   no longer gated behind any further authorization beyond the request
   itself.
2. **Approval is not merge authority.** `APPROVE` must not automatically
   mean `MERGE`. Merge authority is never inferred from a clean verdict or
   a submitted approval — see "Merge boundary" below.
3. **Agent-controlled input cannot manufacture reviewer independence or
   GitHub permission.** Flags, prompts, CLI arguments, generated
   instructions, nested Skill or nested agent instructions, environment
   variables, alternate credentials, alternate usernames, and
   orchestration metadata supplied or reachable by the agent performing or
   orchestrating the review can never establish reviewer independence
   (principle 4) or substitute for genuine GitHub review/event permission
   — individually or combined. They also can never turn a self-review into
   a mutating one (principle 6/self-review boundary below).
4. **Reviewer independence requires authority separation, not only
   identity separation.** Two different GitHub usernames are not
   automatically two independent reviewers. A different identity under
   the same controlling authority is the same reviewer for this policy's
   purposes.
5. **An implementation agent cannot manufacture its own reviewer.**
   Switching GitHub accounts, selecting another token, using a bot, a
   service account, or a GitHub App identity, invoking a nested agent,
   spawning another process, or forwarding instructions to another
   reviewer still under its own authority must not bypass self-review
   protection.
6. **Ambiguous mode, reviewer provenance, or GitHub permission must fail
   closed.** Any doubt about which publication mode is in effect, whether
   a reviewer is independent, or whether the identity holds the needed
   GitHub event permission, resolves to the non-mutating (`passive`)
   outcome for that action.
7. **Existing review-integrity guarantees remain intact** — exact
   reviewed-HEAD validation, stale-review protection, reviewer
   ownership, delta re-review semantics, P0/P1/P2 severity behavior,
   unresolved blocking-finding handling, and the mutation/security
   boundary. This gate composes with them; it never substitutes for or
   relaxes them.
8. **This policy authorizes review-publication outputs only.** It governs
   inline review comments, the consolidated review body, and the
   `APPROVE` / `REQUEST_CHANGES` / informational `COMMENT` events — never
   file modification, patch application, commit, push, merge, repository
   settings changes, arbitrary issue mutation, mutation of an unrelated
   PR, runtime sandbox capability, or agent spawning. Those are governed
   by this source repository's own canonical threat model and
   authority-capability model (development-time
   issues [#298](https://github.com/amirbena/code-review-skill/issues/298)
   and [#301](https://github.com/amirbena/code-review-skill/issues/301),
   outside this packaged Skill), which this policy references rather than
   re-derives — see "Authority boundary" below.

## Self-review is allowed; self-approval is not

Analysis eligibility and mutation eligibility are **separate**:

```text
analysis_allowed                → may this reviewer run the review at all?
formal_review_mutation_allowed  → may this reviewer submit a formal
                                  APPROVE / REQUEST_CHANGES event?
```

Authorship gates only the second. When the reviewer is the PR author, or
is a reviewer under the same controlling authority as the author (an
alternate account / token / bot / service account / GitHub App identity /
nested agent / spawned process — see
[`review-authority.md`](review-authority.md), "Authority separation, not
just identity separation"), the invocation is a **self-review**:

```text
analysis_allowed               = true
formal_review_mutation_allowed = false
```

The full review runs — same evidence, same process, same mechanical
verdict derivation — and produces the outcome (both the clean and the
blocking case) documented in full by
[`review-authority.md`](review-authority.md), "Self-review capability"
(its "Example outcomes" block): a reported `REVIEW CLEAN` /
`CHANGES REQUIRED` verdict, an optional informational `COMMENT`
publication, and a withheld formal decision. That policy is the
canonical owner of the worked example; it is not repeated here.

This boundary is **absolute for a self-review** — `APPROVE` on one's own
work is **always** forbidden, and no publication mode,
natural-language request, flag, prompt, or trusted external authorization
can make a self-review submit a formal event (`APPROVE` / `REQUEST_CHANGES`). The reviewer-independence rules below decide whether an
**external** (non-self) review may mutate; they never apply to a
self-review, which is non-mutating by construction. `MERGE` is never
introduced here for any reviewer.

## Publication modes (canonical)

There are exactly **three** publication modes. They are the single,
canonical answer to "should this review actually be published?" — every
other place in this Skill that used to ask that question independently
(the pre-#314 review-action mode) now only reads this one switch; see
"Migration from the pre-#314 model."

```text
PASSIVE  active-review execution = false   publication = false
SEMI     active-review execution = true    publication = false
ACTIVE   active-review execution = true    publication = true
```

`active-review execution` is whether the full active-review decision path
runs (HEAD tracking, GitHub-permission probing, the mechanical
verdict-to-event mapping). `publication` is whether the resulting event
(`APPROVE` / `REQUEST_CHANGES`, plus its review body and inline comments)
is actually submitted to GitHub. Passive review is documented in
[`../runbooks/passive-pr-review.md`](../runbooks/passive-pr-review.md);
semi and active review share one decision path, documented together in
[`../runbooks/active-pr-review.md`](../runbooks/active-pr-review.md),
which the caller's requested mode steers to a submitting or
non-submitting finish.

Users express intent in natural language — see "Natural-language
publication intent" below — and there is no required user-facing mode
syntax (no `--passive` / `--semi` / `--active` flag is required, though
these three words, and closely equivalent phrasing, are recognized).
Exactly one mode is in effect for an invocation. The mode never changes
which findings exist, their severity, or the derived decision — it only
governs whether, and how, the result reaches GitHub.

### PASSIVE (default)

Performs the full review and produces the complete finding set, the
mechanical decision, and the human-facing report. Performs **no** GitHub
review mutation of any kind: no inline comments, no review body
submission, no `APPROVE`, no `REQUEST_CHANGES`, no informational
`COMMENT`. The verdict and findings are returned to the caller only.

Passive is the default when the caller's intent cannot be resolved to
`semi` or `active` (see "Safe default and fail-closed"). It never
"upgrades" itself.

### SEMI

Runs the **same** active-review decision path as `ACTIVE` — same PR
scope, same HEAD tracking, same GitHub-permission and reviewer-
independence resolution, same mechanical verdict-to-event mapping — but
**suppresses GitHub publication**: no inline comments, no review body, no
`APPROVE`, `REQUEST_CHANGES`, or `COMMENT` is submitted. It is a
preview/dry-run of what `ACTIVE` would do, not a second flavor of
`PASSIVE`: the caller sees the exact event that would have been
submitted (`Would publish: APPROVE` / `Would publish: REQUEST_CHANGES`)
and the exact findings/body/inline-comment content that would have
accompanied it, computed by the identical process `ACTIVE` uses.

Because `SEMI` never publishes, it needs no reviewer-independence or
GitHub-permission resolution to produce its "would publish" report — but
when those facts are available (e.g. already resolved from context), they
are still surfaced for transparency, exactly mirroring what `ACTIVE` would
report as `Mutation: WITHHELD (...)` if the same facts held there.

### ACTIVE

Runs the active-review decision path **and submits its outcome to
GitHub**. This is the mode in which the **core invariant** below applies.

## Core invariant: an explicit ACTIVE request is its own authorization

**When the caller explicitly requests `ACTIVE` review, that request is,
by itself, sufficient authorization to publish the review's own outcome.**
No second activation phrase, approval prompt, out-of-band confirmation,
or "did you really mean active?" gate is required or consulted. Concretely,
for an `ACTIVE` invocation that is **not** a self-review, whose reviewer
is independent (see "Trusted reviewer independence" below), whose GitHub
identity holds the needed event permission, and whose reviewed HEAD is
still current:

- `ACTIVE` + `REVIEW CLEAN` → `APPROVE` is submitted.
- `ACTIVE` + unresolved blocking findings → `REQUEST_CHANGES` is
  submitted.

This is the single place the invariant is enforced — the mutation
resolution in
[`review-output.md`](review-output.md), "Review-action authorization
gate," and this source repository's own test-only reference model
(`tests/reference/review/review_action_authorization.py`, outside this
packaged Skill) — and every other document in this Skill defers to it
rather than re-deriving it.

This invariant does **not** bypass, weaken, or shortcut any of:

- the **self-review boundary** above (absolute; `ACTIVE` still submits no
  formal event on the reviewer's own work);
- **trusted reviewer independence** (below; a different username under the
  same controlling authority is still the same reviewer);
- **GitHub review/event permission** (a caller can request `ACTIVE` all it
  likes; it still cannot submit an event its authenticated identity is not
  permitted to submit — see
  [`review-authority.md`](review-authority.md), "Review/repository access
  prerequisite");
- **HEAD revalidation** (a stale reviewed HEAD is never approved; see
  [`review-output.md`](review-output.md), "HEAD revalidation");
- the **mechanical severity → decision derivation**
  ([`../../../shared/policies/severity.md`](../../../shared/policies/severity.md));
- the **authority boundary** (below): publication authority never expands
  into file modification, patch application, commit, push, merge,
  repository settings, or any capability outside the review-publication
  outputs this policy governs.

An explicit `ACTIVE` request removes exactly one thing relative to the
pre-#314 model: the requirement for a *second*, independently-sourced
authorization signal once the caller has already explicitly asked for
active review and every other guarantee above holds. It does not remove
any of those other guarantees.

### Anti-regression guard

The following state must never be reachable for an invocation that
explicitly requested `ACTIVE`, passed self-review/independence/permission,
and reviewed a current HEAD:

```text
REVIEW CLEAN
decision = APPROVE
mutation = WITHHELD because activation missing
```

If the reasoned decision is `APPROVE` and every guard above is satisfied,
the mutation is `SUBMITTED (APPROVE)` — never `WITHHELD` for a missing
second activation signal. This is enforced by construction: the resolver
in `review_action_authorization.py` has no parameter, flag, or code path
that represents a "trusted mutation authorization" independent of the
requested mode, so there is nothing left in the model that could produce
this state. See this source repository's
`tests/unit/review/test_review_action_authorization.py` (outside this
packaged Skill), `ActiveRequestIsSufficientAuthorization`, for the
regression test.

## Safe default and fail-closed

- The default mode is **`PASSIVE`**. A review with no clearly resolved
  `SEMI` or `ACTIVE` intent performs no GitHub mutation of any kind.
- A caller does **not** need to pass anything, or say "do not approve",
  to get safe autonomous-agent behavior. Silence means `PASSIVE`.
- Ambiguity fails closed. If the intended mode is unclear, or reviewer
  provenance is ambiguous, the invocation resolves to `PASSIVE` for an
  unclear mode, or to a `WITHHELD` mutation (verdict still reported) for
  an `ACTIVE` request whose independence/permission/HEAD facts are
  ambiguous or unfavorable. It never proceeds with a mutation on partial
  or ambiguous evidence.
- A withheld mutation is reported explicitly with its reason (see
  "Reporting"), never silently downgraded.

## Trusted reviewer independence

Reviewer independence is a question of **authority**, not usernames, and
is unchanged by #314 — it is exactly as required for `ACTIVE` publication
as it was for the pre-#314 `explicitly-authorized auto-action` mode.

`authenticated_identity != pr_author_identity` (the check owned by
[`review-authority.md`](review-authority.md), "Self-review capability") is
**necessary but not sufficient**. Failing it means the invocation is a
self-review: analysis still runs, and the formal event is withheld.
Passing it does not by itself establish independence — it is not the
whole trust model.

An actor is **not** an independent reviewer, and using it does not create
reviewer independence, when its selection, credentials, or instructions
are controlled by the agent that implemented or is orchestrating the
change under review. In particular, the following do not manufacture an
independent reviewer:

- switching to another GitHub account the agent controls;
- selecting or presenting another token or credential;
- using a bot account, a service account, or a CI identity the agent can
  drive;
- using a GitHub App identity the agent can act as;
- invoking a nested agent, sub-agent, or "reviewer" role the agent spawns
  and controls;
- spawning another process under the same controlling authority;
- forwarding the review task, with instructions, to another agent that
  remains under the first agent's authority.

A reviewer is independent only when its authority to review — its
identity, its decision to run, and its instructions — originates outside
the implementing/orchestrating agent's control. When reviewer provenance
cannot be established with confidence, treat it as **not independent** and
fail closed; do not assume independence for convenience.

This is distinct from Agent review *ownership*
([`../../../shared/policies/review-ownership.md`](../../../shared/policies/review-ownership.md),
"Access vs. Ownership"): ownership asks whether another Code Review Agent
already holds this scope; independence asks whether *this* reviewer's
authority is separate from the change's author. Both must hold
independently for a privileged action.

## Natural-language publication intent

Users express what they want in ordinary language. The Skill normalizes
that intent to one of the three modes; it never requires the user to name
a mode or pass a flag.

```text
"Just review this PR."                              → PASSIVE
"Review it and tell me what would happen, but       → SEMI
 don't touch GitHub."
"Review it; approve if clean, request changes if    → ACTIVE
 there are blocking findings."
"Actively review PR #123."                          → ACTIVE
```

When the phrasing is ambiguous, or cannot be mapped to one clear mode,
resolve to `PASSIVE` per "Safe default and fail-closed." An `ACTIVE`
request is a real, effective request for publication (see "Core
invariant" above) — it is not merely a *candidate* awaiting a second
signal. It is still subject to the self-review, independence, permission,
and HEAD guarantees enumerated there.

## Authority boundary

This policy authorizes **review-publication outputs only**: inline review
comments, the consolidated review body, `APPROVE`, `REQUEST_CHANGES`,
informational `COMMENT`, and other already-defined GitHub review-
publication artifacts owned by
[`review-output.md`](review-output.md). Nothing in this policy — including
the core invariant above — authorizes:

- file modification or patch application;
- `commit` or `push`;
- `merge`;
- repository settings changes;
- mutation of an issue, or of a PR other than the one under review;
- runtime sandbox capability beyond what
  [`../../../shared/policies/runtime-validation.md`](../../../shared/policies/runtime-validation.md)
  already permits for read-only reproduction;
- spawning another agent.

These capabilities are governed by this source repository's own canonical
threat model and its authority/mutation-capability model (development-time
documentation outside this packaged Skill), specifically the `AUTH-###`
capability ladder tracked under
[issue #298](https://github.com/amirbena/code-review-skill/issues/298) and
detailed in [issue #301](https://github.com/amirbena/code-review-skill/issues/301)
(`READ_ONLY → PROPOSE_PATCH → USER_APPROVES → APPLY_PATCH → VERIFY`, with
`COMMIT` / `PUSH` independently authorized). This policy does not
duplicate or weaken that model — it references it. `github-pr-review`
never advances past `READ_ONLY` / `PROPOSE_PATCH` for source code: it
never applies a patch, commits, or pushes, regardless of publication mode.
See also `SKILL.md`, "Mutation Boundary."

## Merge boundary

Unchanged and reaffirmed here because principle 2 depends on it:

- This Skill never merges, and this policy adds no merge capability.
- Merge authority is **never** inferred from a clean verdict or from
  having submitted `APPROVE`.
- A successful `APPROVE` may let a human's or a separate workflow's merge
  proceed under the repository's own rules; performing that merge is
  outside this Skill entirely — see
  [`review-output.md`](review-output.md), "Final decision," and the
  Skill's [`../SKILL.md`](../SKILL.md), "Mutation Boundary."

## Composition with existing guarantees

The gate is applied **in addition to**, and after, everything already
required for a formal review:

```text
self-review mutation boundary (review-authority.md) — authorship forbids a
                                                 formal self-review event;
                                                 analysis still runs
    ↓
reviewer ownership (review-ownership.md)        — REVIEW ALREADY OWNED unchanged
    ↓
review/repository access + event capability     — GitHub permission unchanged
    ↓
review mode (reviewer-delta-review.md)          — full vs. delta unchanged
    ↓
complete scope, findings, severity, verdict      — mechanical derivation unchanged
    ↓
HEAD revalidation (review-output.md)             — stale HEAD never submitted
    ↓
PUBLICATION MODE RESOLUTION (this policy)        — PASSIVE | SEMI | ACTIVE
    ↓
reviewer independence (this policy)              — required for ACTIVE publication
    ↓
submit permitted mutation (ACTIVE only), or withhold it and report the verdict
```

If any earlier step withholds or blocks a formal review, this gate does
not re-enable it. If this gate withholds a mutation, the earlier
reasoning result still stands and is still reported.

## Reporting

Report the review verdict and the mutation outcome **separately**, so a
withheld mutation is never mistaken for a verdict and vice versa. In
addition to the reasoning/comments/decision lines in
[`review-output.md`](review-output.md), "Final decision," an active or
semi invocation states:

```text
Publication mode: PASSIVE | SEMI | ACTIVE
Mutation:         SUBMITTED (<event>) | WOULD PUBLISH (<event>) | WITHHELD (<reason>) | NOT REQUESTED
```

`WOULD PUBLISH (<event>)` is used only in `SEMI` mode, reporting the exact
event `ACTIVE` would have submitted, without submitting it.

`WITHHELD` reasons are explicit and name the specific gate that stopped
the mutation, for example:

- `WITHHELD (self-review: reviewer is the PR author; no formal review event on own work)`
- `WITHHELD (reviewer independence not established)`
- `WITHHELD (GitHub event permission not held by this identity)`
- `WITHHELD (reviewed HEAD is stale; re-reviewing the new delta)`
- `WITHHELD (publication mode is PASSIVE)`

A clean verdict with a withheld approval is reported as exactly that: a
clean reasoning result **and** a non-mutating outcome. It is never
rendered as "approved."

## Migration from the pre-#314 model

The pre-#314 model used two independent switches: the passive/active
review-type axis, and a secondary `recommendation-only` /
`block-only` / `explicitly-authorized auto-action` "review-action mode"
that additionally required an out-of-band "trusted mutation
authorization" signal before `APPROVE` could ever be submitted, even for
an explicitly requested active review. Issue #314 removes that secondary
switch from the normal publication path entirely:

- **`recommendation-only`** is now simply `PASSIVE` (default, and the
  fail-closed outcome for `ACTIVE` requests that don't clear
  independence/permission/HEAD) — no independent, user-settable "mode"
  remains; a caller no longer needs to say or avoid saying anything to get
  this outcome.
- **`block-only`** is removed as a mode. It existed solely to let a
  blocking result publish `REQUEST_CHANGES` while withholding `APPROVE`
  for a clean one, under the old model's belief that clean-result
  publication needed a *stronger* authorization than blocking-result
  publication. Under the new model there is exactly one publication
  authorization question — "is this `ACTIVE`, and do independence/
  permission/HEAD hold?" — and it answers identically for both outcomes;
  there is no longer a scenario where `REQUEST_CHANGES` is authorized but
  `APPROVE` is not, for the same otherwise-qualifying `ACTIVE` invocation.
  A caller who explicitly wants only the blocking behavior (e.g. "block it
  if there are serious issues, but don't approve it") is making a
  content-level request about which specific event to submit, not
  requesting a different authorization mode; that preference is honored as
  ordinary natural-language scoping of the `ACTIVE` request (see
  [`review-output.md`](review-output.md), "Final decision"), the same way
  a caller can scope any other part of a request — it is not a fourth
  publication mode and does not reintroduce a second authorization gate.
- **"Trusted mutation authorization"** (the provenance/channel machinery —
  agent-controlled channels, independent-trusted channels, authorization
  scope-and-replay binding) is removed from the normal publication path.
  The "Structural limitation" this concept used to document — that a
  portable, runtime-less Skill cannot cryptographically verify where a
  string came from — is now moot for publication, because publication no
  longer depends on verifying the provenance of a second signal: the
  caller's own explicit `ACTIVE` request, verified the same way any other
  invocation content is (it is what the caller asked for in this
  invocation), is the whole of what "authorization" means here. What still
  *does* require independent verification — reviewer independence and
  GitHub event permission — is unchanged and is not weakened by this
  removal.
- **`explicitly-authorized auto-action`** is now simply `ACTIVE`. An
  `ACTIVE` request is real, effective, and immediately actionable (subject
  to the unchanged guards); it is not a mere "candidate" awaiting a second
  channel.
- **`SEMI`** is new: a non-mutating preview of the exact `ACTIVE` decision
  path, requested when the caller wants to see what would publish without
  touching GitHub.

Nothing about the self-review boundary, reviewer-independence
requirement, GitHub-permission requirement, HEAD revalidation, or the
mechanical severity → decision derivation changed. Those guarantees are
restated, not weakened, throughout this document.
