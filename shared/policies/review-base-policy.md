# Shared Policy — Review-Base Policy Compliance

Applies identically to `local-code-review` and `github-pr-review`. It owns
one repository-relative invariant: when the change under review targets an
integration base that reliably, evidencedly violates the target
repository's own review-base policy, that is a workflow/repository-policy
violation independent of implementation findings, and is reported as
exactly one blocking finding — never as a second, competing review-base
model, and never by hardcoding a branch name.

This is not a second scope, evidence, or severity model:
[`review-scope.md`](review-scope.md) still owns what is examined and how
implementation findings are reasoned about, [`evidence.md`](evidence.md)
still owns the confirmed-defect / credible-engineering-risk labeling, and
[`severity.md`](severity.md) still owns the P0/P1/P2 definitions and the
mechanical decision derivation. This policy only adds one narrowly scoped
check that runs before those, using inputs ([`repository-instructions.md`](repository-instructions.md)'s
discovery mechanism, and, for `github-pr-review`, the PR's own base-ref
resolution) that already exist.

## Repository-resolved review base

The **repository-resolved review base** is the branch the target
repository's own policy designates as the correct integration target for
the change under review. It is resolved, never assumed, from one of two
ranked signals:

1. **An explicit, discoverable statement in the target repository's own
   instructions** — an applicable `AGENTS.md`/`CLAUDE.md`, or a document
   either of those names as authoritative (for example a contribution
   guide), naming the branch changes of this kind must integrate into.
   Discover it exactly as
   [`repository-instructions.md`](repository-instructions.md)'s
   "Normalized Repository Instruction Context" already resolves
   repository-local instructions for the review — this policy introduces
   no second discovery mechanism, and never re-reads instruction files
   that step has not already surfaced.
2. **Absent an explicit statement**, the repository's actual configured
   default/target branch, when it can be established from a reliable,
   repository-native signal (see "Per-Skill resolution" below).

When neither signal resolves cleanly, or the two signals conflict with no
stated precedence between them, the repository-resolved review base is
**unknown**. An explicit statement, when one exists, is authoritative over
the bare default/target branch — a repository is free to require
integration into a branch other than its configured default.

## Fail-closed on an unresolved base

When the repository-resolved review base cannot be established reliably,
or the base under review itself cannot be established reliably, this
policy emits **nothing** — no finding, no invented branch name, and no
placeholder naming a guessed branch. Reporting a violation the evidence
does not actually support is worse than reporting nothing; an unresolved
base is a valid terminal outcome, not a reason to guess. This is the same
fail-closed discipline [`api-contract-compatibility.md`](api-contract-compatibility.md)
and [`review-scope.md`](review-scope.md)'s "Semantic change-implication
reasoning" already apply to insufficient evidence, not a new evidence
standard invented for this policy alone.

**Git `HEAD` is never substituted as the repository-resolved review base
merely because it is `HEAD`.** `HEAD` identifies the reviewed change, not
the repository's integration policy; the two are resolved independently,
and neither may stand in for the other when the actual base cannot be
established.

## Per-Skill resolution

- **`github-pr-review`** — the base under review is the PR's own declared
  base ref, resolved exactly as `repository-checkout.md`'s "Base / head
  fidelity" already requires. When `stacked-pr-review.md` resolves the PR
  as a stack layer, this check applies to the stack's **root** (the
  repository's default/target branch that policy's chain terminates at)
  once topology resolution reaches it — never to an intermediate layer's
  own parent-PR base, which `stacked-pr-review.md` already treats as
  legitimate by definition. When that policy's Tier 1 or Tier 2 fallback
  applies because topology itself could not be resolved reliably, the base
  under review for this check is exactly the declared base that fallback
  used — an unresolved *stack* is not, by itself, evidence of a *policy*
  violation, and this check does not compound one unresolved-topology
  signal into a second, speculative finding. Retargeting a PR's base
  branch, changing branch protection or required checks, and publishing a
  GitHub status/check for this outcome are explicitly out of scope for
  this policy (see "Non-goals").
- **`local-code-review`** — the base under review is the review base this
  Skill's own runbook already resolves per `repository-state.md`.
  The repository-resolved review base is established per the ranked
  signals above: an explicit repository-stated policy first, otherwise the
  local repository's own configured remote default-branch signal (for
  example, the branch a remote's `HEAD` points at) when that signal is
  present and unambiguous. A caller-supplied review base for this
  invocation is honored as the base under review exactly as existing
  contracts already allow — this policy evaluates whatever base the
  runbook resolved; it does not independently re-resolve or second-guess
  it. When no explicit statement exists and the default-branch signal is
  absent, ambiguous, or unavailable (for example, no configured remote),
  the repository-resolved review base is unknown and this policy is
  silent, per "Fail-closed on an unresolved base."

## Violation check and finding

Once both the base under review and the repository-resolved review base
are independently and reliably known, compare them. When they differ, and
the difference is not itself the legitimate stacked-PR case above, emit
**exactly one** finding:

- **Severity: P0**, per [`severity.md`](severity.md), "P0 — Critical /
  Blocking" — an unsafe-to-merge integration target is a workflow
  violation independent of the change's own implementation quality.
- **Naming both branches explicitly**: the actual base under review, and
  the repository-resolved review base it should have targeted. Never a
  generic "wrong base branch" statement with no named branches.
- **Emitted before implementation findings.** This check runs, and its
  finding (if any) is recorded, before the review's implementation-focused
  reasoning under [`review-scope.md`](review-scope.md) begins — see each
  Skill's own runbook for the exact step placement. This governs *when the
  finding enters the finding set*, not the mechanical decision derivation:
  [`severity.md`](severity.md)'s decision derivation still runs exactly
  once, over the complete finalized finding set, unchanged by this policy.

A repository with no discoverable review-base policy, or whose declared
base already matches the repository-resolved review base, produces no
finding from this policy — this is the ordinary case for the overwhelming
majority of reviews, exactly as [`api-contract-compatibility.md`](api-contract-compatibility.md)
produces no finding for the overwhelming majority of changes with no
implicated contract.

## Non-goals

- Retargeting or editing a PR's base branch.
- Changing GitHub branch protection, rulesets, or required checks.
- General branch-naming validation unrelated to the review base.
- Publishing a GitHub status/check for this outcome.
- A second Review Target / Review Context / Repository Context model —
  those concepts, where they apply, remain owned by
  [`review-context.md`](review-context.md) and
  [`review-ownership.md`](review-ownership.md); this policy consumes
  them where already resolved and does not redefine them.

## Relationship to existing policies

- [`repository-instructions.md`](repository-instructions.md) owns
  discovery of the target repository's own instruction files; this policy
  reuses that discovery for the explicit-statement signal and does not
  duplicate it.
- `stacked-pr-review.md` (`github-pr-review`'s own policy) owns
  stack-topology detection, the effective review base for a stack layer,
  and safe failure when topology cannot be resolved; this policy applies
  only to the resolved root, never to an intermediate layer's parent-PR
  base, and never treats an unresolved-topology fallback as a
  policy-violation signal by itself.
- `repository-state.md` (`local-code-review`'s own policy) owns how that
  Skill resolves the review base for its own Git-mechanics purposes; this
  policy evaluates that resolved value and does not redefine it.
- [`severity.md`](severity.md) owns the P0/P1/P2 definitions and the
  mechanical decision derivation, applied to this policy's finding exactly
  like any other finding.
