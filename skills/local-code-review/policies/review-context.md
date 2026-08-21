# Policy — Optional Review Context

This Skill's own policy for the **optional** case where the caller
supplies additional context describing the intended change alongside the
local review request — free-form text, requirements, a Jira ticket and
its acceptance criteria, an HLD/architecture/ADR note, an implementation
plan, a bug/incident description, a PR/task description, or similar. This
file is the single canonical owner of that behavior;
[`../SKILL.md`](../SKILL.md) and
[`../runbooks/local-review.md`](../runbooks/local-review.md) state the
concise behavioral consequence and reference this file rather than
redefining it.

**If no review context is supplied, this file does not apply and nothing
in this Skill's behavior changes.** Everything below is additive and
strictly conditional on the caller providing one. This Skill never asks
the user to supply context when none was given — it is purely opt-in.

## Why this exists

A diff alone answers "what changed," not "what was this change supposed
to accomplish, and therefore what should be inspected carefully." When
the caller has requirements, acceptance criteria, an HLD, or a ticket
already in hand, supplying it lets this Skill focus its attention on the
execution paths, invariants, and regressions that actually matter for
this change, instead of reconstructing intent from the diff alone.

```text
Local Delta
  +
Supplied Review Context (intended behavior, acceptance criteria,
                          invariants, constraints, non-goals)
      ↓
 Context Understanding
      ↓
Focused Review of the Local Delta
      ↓
Final local-code-review decision
```

This is not a requirements audit and not a second complete review pass
over the surrounding system. It is a targeted focusing step that informs
the one local review this Skill always performs — the review's object
remains the current local delta.

## Input form

Review context is optional and free-form. It may arrive as:

- free-form text describing the intended change;
- user-provided requirements;
- a Jira (or equivalent tracker) ticket's description and/or acceptance
  criteria;
- an HLD, architecture/design document, or ADR;
- an implementation plan;
- a bug description or incident follow-up;
- a PR/task description;
- migration, security, performance, or rollout requirements/constraints.

No source requires a dedicated integration. At this Skill's boundary,
any of the above is simply review context — the caller supplies the text
(pasted, attached, or otherwise made available), and this Skill treats it
uniformly regardless of which of the above categories it came from. A
caller may optionally label the source (e.g. "Context source: Jira
BILLPAY-1234") to aid traceability; an unlabeled, purely free-form block
of text is equally valid input.

## Recommended internal normalization

Prefer normalizing supplied context into a small internal structure
rather than scattering raw text through review reasoning — illustrative,
not a mandatory schema; use whatever representation fits the reasoning
actually being done, and skip structure entirely for a short, already-
concrete context block:

```text
ReviewContext
- source_type: optional (free-form | requirements | jira | hld | adr |
  implementation-plan | bug-description | incident-followup |
  pr-description | other)
- source_name: optional (e.g. "BILLPAY-1234", "Payments HLD")
- raw_context: the supplied text
- intended_behavior: what the change is supposed to accomplish
- acceptance_criteria: explicit pass/fail conditions, if stated
- constraints / invariants: things that must remain true
- explicit_non_goals: what the context says is out of scope
```

## Evidence hierarchy

Review context describes *intended* behavior. It never substitutes for
verifying *actual* behavior. When context and other sources disagree, or
when context claims something the code should do, this Skill resolves it
using this precedence, strongest first:

1. actual code / diff / tests / configuration;
2. repository-local instructions and architecture (`AGENTS.md`,
   `CLAUDE.md`, discovered per
   [`repository-instructions.md`](../../../shared/policies/repository-instructions.md));
3. explicit task/review context supplied to this Skill (this policy);
4. reviewer inference.

Concretely:

- Do not state that something is implemented merely because the supplied
  context says it should be — inspect the implementation.
- Do not let context override clear repository evidence to the contrary;
  see "Context mismatch vs. implementation defect" below.
- Context may legitimately fill gaps the diff alone can't answer (why a
  change exists, what "correct" means for it) — that is its proper use.

## Using context to focus review attention

When context exists, derive review targets from it rather than treating
it as background color. For example:

- **"Validation must happen before any external execution"** → focus on
  validation location, call ordering, bypass paths, recurring/retry
  flows, post-approval flows, error handling, and tests proving no
  execution occurs before validation.
- **"Processing is at-least-once"** (HLD) → focus on idempotency,
  duplicate-event handling, retry behavior, transactional boundaries, and
  side effects.
- **"Existing behavior X must remain unchanged"** (acceptance criterion)
  → focus on regression risk, shared validation paths, branching logic,
  and existing tests covering X.
- **"Partition/ownership assignment must remain stable"** (architecture
  note) → focus on key derivation, deterministic ownership, accidental
  reassignment, fallback logic, and writes through alternate access
  paths.

Context shapes *what the reviewer looks for*, never *what conclusion the
reviewer is forced to reach*. A requirement is a lens for inspection, not
a preloaded verdict — the review step
([`../runbooks/local-review.md`](../runbooks/local-review.md), the review
step) still independently determines, from the actual delta, whether the
described behavior holds.

## Context mismatch vs. implementation defect

Reason carefully about discrepancies between context, repository
behavior, the current diff, and tests. Distinguish:

- **Implementation clearly violates an explicit requirement** — report a
  finding, with severity based on actual impact per
  [`severity.md`](../../../shared/policies/severity.md), never inherited
  from the context's own emphasis or wording.
- **Context appears stale or conflicts with repository architecture** —
  do not automatically treat the implementation as wrong. State the
  conflict and the evidence on each side; let the reader judge which is
  authoritative. This is a note, not an automatic finding against either
  side.
- **Requirement is ambiguous** — do not invent a missing requirement or
  guess at intent. Report the ambiguity when it is material to a finding
  rather than silently resolving it one way.
- **Context describes work outside the current diff** — do not demand
  unrelated implementation merely because the context mentions it. Only
  raise it when the current change creates a regression against it or was
  explicitly expected to complete that requirement (per the context
  itself or the diff's own apparent intent).

## Scope discipline: no scope explosion

Optional context exists to improve precision, not to turn every review
into a complete architecture or requirements audit:

- Review the current change; use context to identify relevant execution
  paths, invariants, acceptance criteria, architectural boundaries,
  regressions, missing tests, and edge cases *within that change*.
- Do not start reporting unrelated pre-existing architecture problems
  merely because an HLD or design document mentions the surrounding
  system.
- Existing scope and delta-review rules — see
  [`review-scope.md`](../../../shared/policies/review-scope.md) and
  [`evidence.md`](../../../shared/policies/evidence.md), "Findings beyond
  the changed lines" — remain fully authoritative; this policy narrows
  attention within that scope, it never widens the scope itself.

## Explicit non-goals

When supplied context states something is explicitly out of scope for
this change (e.g. "do not implement key migration/failover between
shards"), that statement is itself useful review context: it prevents
this Skill from treating the corresponding gap as a missing-implementation
finding, and it should not be exploited to wave away a genuine regression
the current change introduces. A stated non-goal narrows what's expected
to be *built*; it never narrows what's expected to be *safe*.

## Tracing findings back to context

When a finding comes specifically from supplied context — i.e. it would
not have been raised, or its severity would not be justified, without
that context — make the relationship visible in the finding's own
Evidence, per
[`../../../shared/templates/finding.md`](../../../shared/templates/finding.md):

```text
P1 — Validation can be bypassed in recurring-payment execution

Evidence:
Context source: Jira BILLPAY-1234, acceptance criteria — "CC/RTP
validation before every execution path." <concrete code evidence that
the recurring-payment path executes without going through that
validation>.

Impact:
...
```

Do not add a context reference to every finding — use it when it
materially explains why the behavior is incorrect or risky, exactly as
[`pr-context.md`](pr-context.md) does for PR-context-derived findings.
This is a provenance note inside the finding's existing Evidence field,
never a second, duplicate listing of the same finding.

## Output

Do not add output noise. Supplied context that had no material effect on
the review is not called out. When context materially shaped the review
— it focused attention that produced a finding, surfaced a mismatch
worth flagging, or its non-goals prevented a false gap being reported —
state it concisely in the optional "Context" section of
[`../templates/local-review-report.md`](../templates/local-review-report.md).
The report's existing shape and decision labels (`REVIEW CLEAN` /
`CHANGES REQUIRED`) are unchanged by this policy; see
[`severity.md`](../../../shared/policies/severity.md), "Decision
derivation (mechanical)" — context informs which findings exist and their
severity classification exactly as any other evidence source would, it
never adds a separate decision path.

## Boundary with invocation approval and mutation boundary

Supplying review context is never itself approval to invoke this Skill,
and never bypasses the per-invocation, current-interaction,
explicit-approval requirement in
[`invocation-approval.md`](invocation-approval.md), which is unchanged
and fully in force. Context is read-only input to this Skill's own
review reasoning; it never grants this Skill any additional capability —
this Skill's [mutation boundary](../SKILL.md) is unchanged, and context
can never authorize editing files, applying patches, committing, pushing,
or any GitHub mutation.

## Backward compatibility

Review context is strictly optional. Existing invocations that supply no
context continue to work exactly as before this policy existed — this
Skill reasons from repository/diff-driven review alone, with no reference
to a missing input.
