# Review-Base Policy Compliance Model

Repository-development design record for **[#134](https://github.com/amirbena/code-review-skill/issues/134)**.
Not packaged; explanatory. It is the canonical home for the
repository-resolved review-base resolution model, the ranked signals, the
fail-closed rule, and the smallest useful first implementation. The
packaged [`shared/policies/review-base-policy.md`](../../shared/policies/review-base-policy.md)
defines the operative rule a reviewer actually applies and references
this document by name; it does not restate this document's rationale or
worked examples.

## 1. Problem and goal

A change under review targets an *integration base* — the branch it is
meant to merge into. When that base violates the target repository's own
review-base policy (for example, a PR opened against a stale or
unintended branch instead of the repository's actual integration target),
the change is aimed at the wrong place: a workflow/repository-policy
violation independent of the change's own implementation quality. Neither
Skill enforced this before #134: `github-pr-review` had the PR's base ref
available but did not evaluate it against repository policy;
`local-code-review` had a "review base" concept
([`repository-state.md`](../../skills/local-code-review/policies/repository-state.md))
with no notion that a wrong base is itself a violation.

The goal is one shared, repository-relative invariant, defined once and
applied identically by both Skills: when the repository-resolved review
base is reliably known and the base under review violates it, emit a
single P0 before implementation findings. When the base cannot be
reliably resolved, emit nothing.

## 2. Why repository-relative, never a hardcoded branch name

A fixed assumption like "the base must be `main`" is wrong for the
common case of a repository whose actual integration branch is `develop`,
`master`, a release branch, or anything else it has chosen. The model
instead resolves the required branch **from the target repository's own
signals** (§3) for every invocation, never from a name baked into policy
prose.

## 3. Ranked resolution signals

1. **Explicit repository-stated policy** — an applicable `AGENTS.md`/
   `CLAUDE.md`, or a document either names as authoritative, stating which
   branch changes of this kind must integrate into. Reuses
   [`repository-instructions.md`](../../shared/policies/repository-instructions.md)'s
   existing discovery; this model introduces no second discovery pass.
2. **The repository's configured default/target branch**, when no
   explicit statement exists. For `github-pr-review`, this is the same
   root [`stacked-pr-review.md`](../../skills/github-pr-review/policies/stacked-pr-review.md)
   already resolves stack topology against. For `local-code-review`, this
   is a reliable, unambiguous local signal — for example, the branch a
   configured remote's `HEAD` points at — never `HEAD` itself, and never a
   guess when no such signal exists.

An explicit statement overrides the bare default branch: a repository is
free to require integration into a branch other than the one it is
configured to treat as default. Neither signal resolving cleanly, or the
two conflicting with no stated precedence, leaves the repository-resolved
review base **unknown** — see §4.

## 4. Fail-closed rule

When the repository-resolved review base, or the base under review
itself, cannot be established reliably, this model produces no finding.
Inventing a violation the evidence cannot support is worse than reporting
nothing — the same discipline the API/contract-compatibility and
dependency/supply-chain deepening models already apply to insufficient
evidence. This is a valid, expected terminal outcome for the large
majority of reviews of a repository with no discoverable review-base
policy stated anywhere and no unambiguous default-branch signal
available (for example, a bare local checkout with no configured remote).

**Worked example — HEAD not substituted.** A local delta reviewed with an
ambiguous or unconfigured remote has no reliable default-branch signal.
The reviewer does **not** fall back to treating the current branch's
`HEAD`, or any other convenient local value, as the repository-resolved
review base merely because it is readily available — that would defeat
the invariant's own purpose, since `HEAD` identifies what is being
reviewed, not what it should integrate into. The correct outcome is
silence, not a fabricated comparison.

## 5. Per-Skill application

- **`github-pr-review`** — applies to the stack's resolved **root** only,
  once [`stacked-pr-review.md`](../../skills/github-pr-review/policies/stacked-pr-review.md)
  has resolved topology. An intermediate stack layer's parent-PR base is
  never treated as a violation — that is the legitimate, by-design
  stacked-PR case. A Tier 1/Tier 2 safe-failure fallback (topology itself
  unresolved) is not, by itself, evidence of a policy violation; it is
  exactly the "base under review cannot be established reliably" case in
  §4.
- **`local-code-review`** — applies to whatever review base the runbook
  already resolved (an explicit caller-supplied base, or the Skill's own
  resolution). This model does not re-resolve or second-guess that
  choice; it only evaluates it against the repository-resolved review
  base from §3.

## 6. Ordering: before implementation findings

The finding this model defines, when it fires, is recorded before the
review's implementation-focused reasoning begins — a dedicated early
runbook step in both Skills (see each runbook's own step numbering),
right after the base/topology resolution each Skill already performs and
before repository-instruction discovery and the actual review. This
governs finding-set *ordering*, not [`severity.md`](../../shared/policies/severity.md)'s
mechanical decision derivation, which still runs exactly once over the
complete finalized finding set.

## 7. Smallest useful first implementation

1. **This model** — the ranked resolution signals (§3), the fail-closed
   rule (§4), and the per-Skill application (§5) — consumed as reviewer
   discipline.
2. **One packaged shared policy** —
   [`shared/policies/review-base-policy.md`](../../shared/policies/review-base-policy.md),
   referenced identically by both Skills' runbooks and `SKILL.md`s, so the
   capability is real in both Skills' review behavior, not only designed.
3. **Contract/drift tests** — asserting both Skills wire the same shared
   policy at the same relative point in their own flow, so they cannot
   silently diverge.

**Deferred** (named here so scope stays fixed):

- Publishing a GitHub status/check for this outcome — separate
  GitHub-native enforcement work
  ([#49](https://github.com/amirbena/code-review-skill/issues/49)).
- A fixture corpus pinning representative repository-resolved-base
  outcomes, analogous to the dependency/supply-chain and API-compatibility
  corpora — quality hardening after this capability exists, not a
  prerequisite for it.

**Rejected alternatives:**

- **Hardcoding `main` as the assumed review base.** Rejected outright —
  contradicts the issue's own acceptance criteria and would produce
  false-positive P0s for the many repositories whose actual integration
  branch is not `main`.
- **Treating any non-default declared PR base as a violation.** Rejected:
  this would misclassify every legitimate stacked-PR review
  ([`stacked-pr-review.md`](../../skills/github-pr-review/policies/stacked-pr-review.md))
  as a policy violation. The model checks the resolved root, not every
  intermediate declared base.
- **Falling back to `HEAD` or the caller-supplied base as the
  repository-resolved review base when nothing else resolves.** Rejected
  per the issue's explicit acceptance criterion and §4's worked example —
  it would compare a value against itself and could never fail closed.

## 8. Relationship to existing canonical policies

- [`repository-instructions.md`](../../shared/policies/repository-instructions.md)
  owns discovery of the target repository's own instruction files; this
  model reuses that discovery and does not define a parallel one.
- [`stacked-pr-review.md`](../../skills/github-pr-review/policies/stacked-pr-review.md)
  owns stack-topology detection and the effective review base for a stack
  layer; this model applies only to the resolved root.
- [`repository-state.md`](../../skills/local-code-review/policies/repository-state.md)
  owns how `local-code-review` resolves the review base for its own
  Git-mechanics purposes; this model evaluates that resolved value.
- [`evidence.md`](../../shared/policies/evidence.md) owns the code-evidence
  bar; this model does not relax it.
- [`severity.md`](../../shared/policies/severity.md) owns severity and the
  mechanical decision derivation; this model classifies its own finding
  as P0 under that file's existing definition and does not touch either.
