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
Resolve External Context
      ├── Jira MCP / connector        (only when a Jira reference is supplied)
      ├── explicit GitHub Issue        (reference → read-only GitHub, or pasted text)
      └── supplied free-form context   (consumed directly, no resolution)
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
if this input did not exist, and never asks the user to provide it. Optional
free-form/textual context that is missing, empty, or not provided is **never**
a reason to fail, block, or degrade the review — the review proceeds on
repository/diff-driven reasoning alone.

A **supplied reference** is different from missing context: see "Reference-based
context requires resolution" below. A Jira reference the caller deliberately
supplied to establish task boundaries, but which cannot be resolved, is not
silently ignored — that invocation's Jira-scoped path stops with an explicit
unresolved report. This does not make Jira mandatory for ordinary reviews.

## Input form

### Textual / free-form context — consumed directly

Any of the following, supplied by the caller as text, is simply review context
— the reviewer treats it uniformly regardless of which category it came from,
with no resolution step:

- explicit user instructions describing intent or focus;
- pasted requirements or acceptance criteria;
- pasted Jira (or equivalent tracker) ticket text — description and/or
  acceptance criteria — when the caller provides the *content*, not just a key;
- a GitHub Issue's pasted description and relevant authoritative comments;
- an HLD, architecture/design document, or ADR (text or excerpt);
- an implementation plan;
- a bug/incident description or follow-up;
- a PR/task description;
- migration, security, performance, or rollout requirements/constraints.

A caller may optionally label the source (e.g. `Context source: Jira
BILLPAY-1234`) to aid traceability; an unlabeled free-form block is equally
valid.

### Reference-based context — requires resolution

A bare **reference** — a Jira ticket key or URL, or a GitHub Issue reference —
is a *pointer to context, not the context itself*. Before it can inform review
reasoning it must be resolved to normalized context:

- a **Jira reference** is resolved per "Jira context resolution" below;
- a **GitHub Issue reference** is resolved through available read-only GitHub
  access (the same access `github-pr-review` uses for PR state); if no such
  access is available, the caller may instead paste the Issue text as
  free-form context. No automatic PR↔Issue discovery.

A reference is never treated as if the identifier itself carried the ticket's
requirements.

## Jira context resolution

When the caller supplies a Jira reference, Jira context is resolved **before**
review reasoning, as an external-context-resolution step:

```text
Review Invocation
      ↓
optional Jira reference
      ↓
External Context Resolution  ──  Jira MCP / connector / equivalent Jira integration
      ↓
Normalized Review Context
      ↓
Review
```

### Capability, not a specific transport

Resolution depends on the capability "resolve Jira context," satisfied by
whatever Jira integration the runtime exposes — a Jira MCP server, a Jira
connector, or an equivalent runtime-exposed Jira read tool. Do not hard-code
review semantics to one transport. If the runtime already exposes a canonical
connector/tool model, use that rather than inventing a new abstraction. The
downstream shared review policies consume the **normalized** context below,
never a raw connector payload.

### Resolution procedure

When a Jira reference is supplied, before any review reasoning that depends on
scope, the reviewer performs these steps in order:

1. **Identify an available Jira-capable integration** — a Jira MCP server, a
   Jira connector, or another runtime-exposed Jira read tool. Use whichever
   the runtime actually exposes; do not require a specific one. If none is
   available, this is a resolution failure ("Resolution is a precondition
   when Jira is supplied" below) — stop, do not proceed as if Jira scope
   were known.
2. **Invoke it in read-only mode** to retrieve the referenced issue by its
   key or URL. "Retrieve" means an actual tool/connector call that returns
   the ticket's contents — never reading the key, the URL, a branch name, a
   PR title, a commit message, or any copied metadata.
3. **Retrieve relevant comments and linked requirement context** through the
   same integration when it supports them — issue comments, linked issues,
   and linked architecture/design references — scoped to what bears on the
   change under review.
4. **Normalize** the retrieved issue and comments into the `ReviewContext`
   shape ("What to retrieve and normalize" and "Jira comments" below) —
   never the raw connector payload.
5. **Continue only after successful resolution.** If step 1, 2, 3, or 4
   fails, do not fall back to the reference text or to inferred context:
   report `JIRA CONTEXT UNRESOLVED` and stop the Jira-scoped path.

This procedure is shared verbatim by both Skills; each runbook references it
rather than restating it, and only the Review Target differs
(`local-code-review` → the local delta; `github-pr-review` → the PR).

### Read-only

Jira access here is **context retrieval only**. This never edits an issue,
transitions it, adds a comment, changes a field, creates a ticket, or assigns
a user. No Jira mutation of any kind is introduced by supplying a Jira
reference.

### What to retrieve and normalize

When the integration supports it, retrieve the task context relevant to
understanding intended behavior and boundaries: issue key, summary,
description, issue type, current status, acceptance criteria, components,
labels, priority (where relevant), parent/epic (where relevant), linked
issues (only where materially necessary), relevant comments, linked
architecture/design information, explicit non-goals, constraints,
clarifications, and settled decisions.

Do not inject the entire raw Jira payload into review reasoning. Normalize
only what informs **intended behavior, task boundaries, requirements,
acceptance criteria, constraints, exclusions, and settled decisions** — into
the same `ReviewContext` shape used for free-form context ("Recommended
internal normalization" below).

### Jira comments

Jira comments can materially improve context, but a comment is **evidence, not
automatically an authoritative requirement**. Classify each relevant comment,
similarly to Existing Review Evidence
([`review-evidence.md`](review-evidence.md)):

- **settled clarification** — an explicit, agreed clarification of intent;
- **accepted decision** — a design/scope decision explicitly concluded;
- **implementation note** — guidance or context, not a pass/fail requirement;
- **unresolved question** — an open question with no agreed answer;
- **speculative suggestion** — an idea floated, not adopted;
- **rejected approach** — an option explicitly declined;
- **superseded discussion** — overtaken by later comments or a decision.

Do not promote every comment into an acceptance criterion. Only a settled
clarification or accepted decision that states an actual pass/fail condition
becomes an acceptance criterion. Prefer a newer explicit maintainer/product
clarification over stale speculative discussion when repository evidence
supports that interpretation.

### Resolution is a precondition when Jira is supplied

- **No Jira reference supplied** → review proceeds normally; nothing here
  applies.
- **Jira reference supplied and resolved** → review proceeds using the
  normalized Jira information as Review Context.
- **Jira reference supplied but not resolvable** — any of: no Jira
  integration is available; authentication fails; authorization fails (the
  identity cannot read the issue); the issue does not exist; the reference is
  malformed; or the integration/connector errors or times out → **do not**
  silently fall back to treating the key/URL as sufficient context, and
  **do not** infer ticket contents from the ticket key, the branch name, the
  PR title, a commit message, surrounding text, or copied issue metadata
  without the ticket's actual contents. The reviewer explicitly reports that
  the supplied Jira context could not be resolved and does **not** perform
  the Jira-scoped review. The concise outcome is `JIRA CONTEXT UNRESOLVED`:
  an explicit incapability report naming the reference and the integration(s)
  attempted, not a graded `REVIEW CLEAN` / `CHANGES REQUIRED` (local) or
  `Approve` / `Request Changes` (GitHub) result. Re-invoking **without** a
  Jira reference yields a normal unscoped review.

This precondition applies only to the Jira-scoped path of that specific
invocation. It never makes Jira required for reviews that do not supply one.

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

- **Read-only.** This policy adds interpretation of supplied text and
  retrieval of referenced context; it never grants either Skill a
  state-changing capability. It can never authorize editing files, applying
  patches, committing, pushing, any GitHub mutation, or any **Jira mutation**
  (editing/transitioning an issue, adding a comment, changing a field,
  creating a ticket, assigning a user) — each Skill's own mutation boundary is
  unchanged, and Jira access is context retrieval only.
- **A reference is not the context.** A Jira key/URL or a GitHub Issue
  reference is a pointer that must be resolved to normalized context before
  use — see "Reference-based context requires resolution." Jira context
  informs scope but never expands the Review Target.
- **Invocation approval unchanged.** Supplying context (a Jira reference or a
  GitHub Issue included) is never itself approval to invoke a Skill and never
  bypasses `local-code-review`'s per-invocation approval contract
  (`skills/local-code-review/policies/invocation-approval.md`) or
  `github-pr-review`'s self-review mutation boundary — authorship still
  withholds a formal `APPROVE` / `REQUEST_CHANGES` on the reviewer's own
  work (`skills/github-pr-review/policies/review-authority.md`).
- **Target unchanged.** Context never converts a Jira ticket, an Issue, an
  ADR, or a PR description into an additional review target. The review target
  stays the local delta / the PR.
