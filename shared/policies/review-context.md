# Shared Policy — Review Context Model

Applies identically to `local-code-review` and `github-pr-review`, in every
mode. It defines the concepts a review reasons over and how optional,
caller-supplied requirement/scope material is used. Each Skill keeps only a
thin policy of its own naming *what its review target is*
(`skills/local-code-review/policies/review-context.md`,
`skills/github-pr-review/policies/review-context.md`); the semantics below are
not restated there.

Existing prior-review material (previous findings, resolved findings, settled
decisions, maintainer clarifications) is a distinct concept with its own
canonical policy — [`review-evidence.md`](review-evidence.md). This file
covers the other three concepts and the requirement-context semantics.

## The four concepts

- **Review target** — the implementation actually under review, and the only
  thing whose defects a decision blocks. `local-code-review`: the local
  implementation delta (committed / staged / unstaged / untracked, per that
  Skill's `repository-state.md`). `github-pr-review`: the GitHub Pull Request
  delta. Context never expands it.
- **Review context** — evidence used to understand the *intended scope and
  requirements* of the change: explicit user instructions, a Jira/tracker
  ticket, acceptance criteria, a GitHub Issue, an HLD, an ADR, an
  implementation plan, a PR/task description, migration/security/performance/
  rollout requirements. Optional. Shapes what the reviewer inspects and what
  "correct" and "in scope" mean for this change. Never a verdict; never a
  substitute for reading the code.
- **Repository context** — surrounding repository evidence needed to judge
  correctness and invariants: `AGENTS.md` / `CLAUDE.md` and other
  repository-local instructions (discovered per
  [`repository-instructions.md`](repository-instructions.md)), architecture
  documentation, related interfaces, surrounding implementation, tests,
  configuration, and repository invariants. Refines *how* the changed code is
  evaluated.
- **Existing review evidence** — previously produced review information that
  may bear on this review — see [`review-evidence.md`](review-evidence.md).

```text
Review Invocation
      ↓
Normalize Inputs
      ├── Review Target        (the delta / the PR — never widened below)
      ├── Review Context       (intended scope & requirements — optional)
      ├── Repository Context   (surrounding code, instructions, invariants)
      └── Existing Review Evidence (prior findings / settled decisions — optional)
      ↓
Shared review policies (review-scope, evidence, severity, file-reviewability)
      ↓
Skill-specific output (local report | GitHub PR review publication)
```

## Review context is optional; its absence changes nothing

Review context is opt-in. When none is supplied, each Skill behaves exactly as
if this input did not exist, and never asks the user to provide it. A missing,
empty, unresolved, or unavailable optional context source is **never** a
reason to fail, block, or degrade the review — the review proceeds on
repository/diff-driven reasoning alone.

## Input form

Any of the following, supplied by the caller as text or a reference, is simply
review context — the reviewer treats it uniformly regardless of which
category it came from:

- explicit user instructions describing intent or focus;
- a Jira (or equivalent tracker) ticket's description and/or acceptance
  criteria;
- a GitHub Issue (description, and relevant authoritative comments — see
  [`review-evidence.md`](review-evidence.md) for the settled-vs-speculative
  distinction, applied identically to Issue discussion);
- an HLD, architecture/design document, or ADR;
- an implementation plan;
- a bug/incident description or follow-up;
- a PR/task description;
- migration, security, performance, or rollout requirements/constraints.

No source requires a dedicated integration; the caller supplies the text
(pasted, referenced, or otherwise made available). A caller may optionally
label the source (e.g. `Context source: Jira BILLPAY-1234`) to aid
traceability; an unlabeled free-form block is equally valid.

For this phase, a GitHub Issue is supplied explicitly (a reference or its
text). There is **no automatic PR↔Issue discovery** in this model — the
linkage, if any, is whatever the caller states.

## Recommended internal normalization

Prefer normalizing supplied context into a small internal structure rather
than scattering raw text through review reasoning — illustrative, not a
mandatory schema; skip structure entirely for a short, already-concrete block:

```text
ReviewContext
- source_type: optional (free-form | user-instructions | jira | github-issue |
  hld | adr | implementation-plan | bug-description | incident-followup |
  pr-description | acceptance-criteria | other)
- source_name: optional (e.g. "BILLPAY-1234", "Payments HLD", "#412")
- raw_context: the supplied text
- intended_behavior: what the change is supposed to accomplish
- acceptance_criteria: explicit pass/fail conditions, if stated
- constraints / invariants: things that must remain true
- explicit_non_goals: what the context says is out of scope
```

## Evidence hierarchy

Review context describes *intended* behavior. It never substitutes for
verifying *actual* behavior. When sources disagree about what the code does,
resolve using this precedence, strongest first:

1. actual code / diff / tests / configuration;
2. repository-local instructions and architecture (`AGENTS.md`, `CLAUDE.md`,
   in-repo ADRs the repository itself treats as canonical — discovered per
   [`repository-instructions.md`](repository-instructions.md));
3. explicit review context supplied to this Skill (this policy) and settled
   existing review evidence ([`review-evidence.md`](review-evidence.md));
4. reviewer inference.

Concretely:

- Do not state that something is implemented merely because the context says
  it should be — inspect the implementation.
- Do not let context override clear repository evidence to the contrary; see
  "Context mismatch vs. implementation defect" below.
- Context may legitimately fill gaps the diff alone can't answer (why a change
  exists, what "correct" means for it) — that is its proper use.

## Using context to focus review attention

When context exists, derive review targets from it rather than treating it as
background color:

- **"Validation must happen before any external execution"** → focus on
  validation location, call ordering, bypass paths, retry/post-approval flows,
  error handling, and tests proving no execution occurs before validation.
- **"Processing is at-least-once"** → focus on idempotency, duplicate handling,
  retry behavior, transactional boundaries, side effects.
- **"Existing behavior X must remain unchanged"** → focus on regression risk,
  shared paths, branching logic, and existing tests covering X.

Context shapes *what the reviewer looks for*, never *what conclusion the
reviewer must reach*. The review still independently determines, from the
actual delta, whether the described behavior holds.

## Context mismatch vs. implementation defect

Reason carefully about discrepancies between context, repository behavior, the
diff, and tests. Distinguish:

- **Implementation clearly violates an explicit requirement** — report a
  finding, severity based on actual impact per
  [`severity.md`](severity.md), never inherited from the context's own
  emphasis or wording.
- **Context appears stale or conflicts with repository architecture** — do not
  automatically treat the implementation as wrong. State the conflict and the
  evidence on each side; let the reader judge. A note, not an automatic
  finding against either side.
- **Requirement is ambiguous** — do not invent a missing requirement or guess
  intent. Report the ambiguity when it is material to a finding.
- **Context describes work outside the current target** — do not demand
  unrelated implementation merely because the context mentions it. Raise it
  only when the current change creates a regression against it or was
  explicitly expected to complete it.

## Scope-boundary reasoning

Context lets the reviewer reason explicitly about the boundary of the
requested change. Where context makes it possible, detect:

- **Required behavior missing** — an acceptance criterion or stated
  requirement the change was expected to satisfy is not implemented.
- **Implementation contradicts acceptance criteria** — the change does
  something the criteria explicitly forbid, or fails a stated pass condition.
- **Unrelated scope expansion** — the change also does something outside the
  requested scope. A finding when the unrelated addition carries real risk or
  violates a stated non-goal / agreed scope; otherwise a noted observation,
  non-blocking unless it independently meets the P0/P1 bar.
- **Valid-but-out-of-scope finding** — a technically real issue that is
  outside the requested change. Still reported when the change introduces or
  activates it; noted as outside the requested scope. A pre-existing,
  unrelated defect merely noticed nearby stays out — see
  [`evidence.md`](evidence.md), "Findings beyond the changed lines."
- **Repository-policy violation** — a repository convention or invariant the
  change breaks. Relevant regardless of ticket scope: a ticket cannot license
  violating the target repository's own stated rules.

### Precedence when scope sources disagree

There is no rigid global priority order. Resolve conflicts by reasoning about
authority and recency, informed by these tendencies:

- **Repository policy and invariants can constrain the implementation even
  when a ticket says otherwise.** A tracker ticket does not override the
  target repository's `AGENTS.md`/`CLAUDE.md` rules or a safety invariant.
- **An accepted ADR/HLD decision generally outweighs speculative ticket
  discussion** on the same design question. A settled decision (see
  [`review-evidence.md`](review-evidence.md), "Settled decisions") is not
  reopened by an offhand comment.
- **Newer explicit maintainer clarification supersedes stale earlier
  discussion.** A later, direct statement of intent wins over an older
  contradictory one.
- Among requirement sources of comparable authority, the **more specific and
  more recently agreed** statement governs (acceptance criteria over a vague
  summary; a PR description that refines a ticket over the ticket's original
  wording).
- Actual code/config always wins on *what currently happens*; these
  precedence notes are about *what the change was supposed to do*.

When a material conflict cannot be resolved from the evidence, report the
ambiguity rather than silently picking a side.

## Explicit non-goals

When supplied context states something is explicitly out of scope (e.g. "do
not implement shard failover"), that statement is useful review context: it
prevents the reviewer from treating the corresponding gap as a
missing-implementation finding. It is never exploited to wave away a genuine
regression the current change introduces. **A stated non-goal narrows what's
expected to be *built*; it never narrows what's expected to be *safe*.**

## Scope discipline: no scope explosion

Optional context improves precision; it never turns a review into a full
architecture or requirements audit. Review the current change; use context to
identify relevant execution paths, invariants, acceptance criteria,
architectural boundaries, regressions, missing tests, and edge cases *within
that change*. Do not start reporting unrelated pre-existing architecture
problems because a design document mentions the surrounding system. Existing
scope and delta-review rules ([`review-scope.md`](review-scope.md),
[`evidence.md`](evidence.md), "Findings beyond the changed lines") remain
authoritative — this policy narrows attention *within* that scope, never
widens the scope itself.

## Tracing findings back to context

When a finding comes specifically from supplied context — it would not have
been raised, or its severity would not be justified, without that context —
make the relationship visible in the finding's own Evidence, per
[`../templates/finding.md`](../templates/finding.md):

```text
P1 — Validation can be bypassed in recurring-payment execution

Evidence:
Context source: Jira BILLPAY-1234, acceptance criteria — "CC/RTP validation
before every execution path." <concrete code evidence that the
recurring-payment path executes without going through that validation>.
```

Use it when it materially explains why the behavior is incorrect or risky —
not on every finding, and never as a second, duplicate listing of the finding.

## Output

Supplied context that had no material effect on the review is not called out.
When context materially shaped the review — it focused attention that produced
a finding, surfaced a mismatch worth flagging, or its non-goals prevented a
false gap being reported — state it concisely in each Skill's optional
context section (see each Skill's own report/summary template). The decision
labels and their mechanical derivation are unchanged by this policy: context
informs which findings exist and their severity exactly as any other evidence
source would — see [`severity.md`](severity.md), "Decision derivation
(mechanical)." It never adds a separate decision path.

## Boundaries

- **Read-only.** This policy adds interpretation of supplied text; it never
  grants either Skill a new capability. It can never authorize editing files,
  applying patches, committing, pushing, or any GitHub mutation — each Skill's
  own mutation boundary is unchanged.
- **Invocation approval unchanged.** Supplying context (including a GitHub
  Issue) is never itself approval to invoke a Skill and never bypasses
  `local-code-review`'s per-invocation approval contract
  (`skills/local-code-review/policies/invocation-approval.md`) or
  `github-pr-review`'s self-review guard
  (`skills/github-pr-review/policies/review-authority.md`).
- **Target unchanged.** Context never converts a Jira ticket, an Issue, an
  ADR, or a PR description into an additional review target. The review target
  stays the local delta / the PR.
