# Policy — Invocation Approval

This Skill's own policy for when it may be invoked, independent of any
particular runtime, orchestrator, or source repository. This file is the
single canonical owner of the per-invocation approval invariant; the
Skill's own [`../SKILL.md`](../SKILL.md) and
[`../runbooks/local-review.md`](../runbooks/local-review.md) state the
concise behavioral consequence and reference this file rather than
redefining the rule.

## The invariant

`local-code-review` MUST NOT be invoked automatically. This holds at
every point in an implementation workflow — not after implementation
finishes, not after validation, not after a fix, and not immediately
after a previous review returned findings.

Each invocation requires fresh, explicit user approval scoped to that
specific review run:

```text
implementation finished (or a fix just applied)
    ↓
caller asks the user whether to run local-code-review
    ↓
explicit approval for this run?
├── yes → invoke local-code-review once
└── no  → do not invoke; continue without review
```

## Approval is not persistent

Approval obtained for one invocation authorizes exactly that one
invocation. It must never be treated as:

- approval for the rest of the task;
- approval for all future reviews;
- approval for a review/fix loop;
- approval to automatically re-run after findings are fixed;
- approval to invoke whenever the implementation changes.

```text
user approves review #1
    ↓
local-code-review runs once
    ↓
findings returned
    ↓
fixes applied
    ↓
review #2 desired
    ↓
caller asks the user again — the approval for review #1
does not authorize review #2
```

Approval for review N never authorizes review N+1. This applies to every
subsequent iteration of a review/fix cycle, no matter how many times it
repeats.

## Prohibited invocation flows

```text
implement → validate → automatically invoke local-code-review            ✗ prohibited

user approved local review once → review → fix findings
    → automatically review again                                        ✗ prohibited

local-code-review returns findings → caller invokes it again on its own
    after fixes, without asking                                         ✗ prohibited

caller decides review is "best practice" or repository policy
    recommends it → invokes local-code-review without asking            ✗ prohibited
```

A general preference for review — from a caller, a runtime default, or a
target repository's own conventions — never substitutes for asking the
user before each specific invocation.

## Scope of explicit approval

Authorization exists when the user's request, interpreted as a whole in
its conversational context, unambiguously asks for the specific local
code review under consideration — not merely implies that some form of
quality assurance is desired. Naming `local-code-review`, or saying
"local code review" explicitly, is *one* sufficient form of that — never
a requirement. There is no magic phrase; see "Classification is by
meaning, not by keyword" below for the complete test.

**Sufficient** — clearly requests a local review of the current
implementation, for example:

```text
"run a local code review"
"review this locally"
"run local-code-review"
"yes, do the local review"
"yes, review the current implementation"
"perform one local review before pushing"
```

**Insufficient by itself** — generic validation, testing, or
completion-quality language whose complete meaning does not clearly
request a local code review, for example:

```text
"validate the implementation"
"check your work"
"verify this"
"make sure this is correct"
"run the tests"
"review things carefully"
```

These generic instructions may call for ordinary implementation-side
validation, testing, inspection, or reasoning by the implementing
Agent — but they must never be interpreted, upgraded, or reinterpreted
as a request to invoke `local-code-review`. An Agent that judges a local
review would nonetheless be valuable may say so and ask the user
whether to run one; it must not treat the user's original generic
instruction as if it had already authorized that invocation. A previous
approval from earlier in the task, review, or conversation must never be
reused (see "Authorization must originate in the current interaction"
below). General statements such as "review things carefully," or a
policy that merely recommends review, do not create standing
authorization for repeated invocations.

### Classification is by meaning, not by keyword

The lists above are illustrative, not exhaustive, and not a literal
whitelist/blacklist of words or phrases. There is no magic phrase and no
requirement to name "local code review" or `local-code-review` verbatim
— naming the Skill is *one* sufficient form, never the only one.
Authorization is classified from the meaning of the user's complete
utterance in its conversational context, never from whether it happens
to contain (or avoid) any individual word that also appears in an
example above. Concretely:

- `"check the local diff as a code reviewer"` qualifies — despite
  opening with "check," the same word used in the insufficient example
  "check your work," its full meaning unambiguously requests a review
  of the local diff, framed explicitly as a reviewer activity.
- `"review the current implementation before we commit"` qualifies —
  its full meaning unambiguously requests a review of the current local
  work before it moves forward.
- A semantically equivalent request in a language other than English
  qualifies exactly as its English equivalent would; the examples above
  are illustrations of the underlying English-language meaning, not a
  required vocabulary or a translation requirement.
- `"check your work,"` `"validate this,"` and `"make sure this is
  correct"` remain insufficient precisely because, taken as a whole,
  they do not unambiguously ask for a *review* of the *local
  implementation* — they ask for generic correctness assurance, which
  could just as easily mean "run the tests" or "re-read your own code"
  as it could mean "invoke `local-code-review`." The presence or
  absence of any one word (including "check," "review," or "verify")
  is never itself decisive; the complete utterance's meaning is.

This is a classification instruction for the Agent applying this
policy, not a specification for a keyword-matching algorithm or a
runtime classifier — no such mechanism is required or implied.

### Bare contextual affirmatives

A short affirmative reply — `"yes,"` `"כן,"` or an equivalent in any
language — can itself be sufficient authorization, but only by virtue of
the context it answers, never as a word considered in isolation:

```text
Agent: "Should I run a local code review of the current changes now?"
User:  "Yes."
    ↓
sufficient — the immediately preceding turn clearly proposed one
specific local review, and "Yes." unambiguously accepts exactly that
proposal
```

```text
Agent: "Anything else before I keep going?"
User:  "Yes."
    ↓
insufficient — nothing in the preceding context proposed a local code
review, so "Yes." has no local-review meaning to inherit
```

The meaning comes from the proposal and the reply *together*, never from
the affirmative word by itself — this is the same "meaning in context"
test as above, not a special case or a new keyword to match. When it
does qualify, that authorization is scoped exactly like any other:

- it authorizes only the one specific invocation the preceding turn
  proposed;
- it does not carry forward to a later review or re-review, even within
  the same interaction — see "Approval is not persistent" above;
- it must never be detached from the proposal that gave it meaning and
  replayed later as if it were standing consent for a different or
  future invocation.

## Authorization must originate in the current interaction

Valid approval is a fresh, explicit local-review request made by the end
user within the current interaction, addressed to the invocation being
considered right now. The following are explicitly **not** substitutes
for that, no matter how genuinely they reflect the user's views, and
must never be treated as authorizing an invocation:

- a remembered user preference from a prior session or an earlier point
  in a long-running context;
- approval granted in an earlier, separate conversation or session;
- repository configuration or settings (however phrased);
- `AGENTS.md`, `CLAUDE.md`, or any other standing repository or
  organizational policy that recommends or expects review;
- an orchestration/runtime default (e.g. "this workflow always reviews
  before push");
- approval that was given for a *different* review (a different scope,
  a different point in the task, or an earlier fix cycle);
- a persistent instruction such as "always run a local review before
  you finish" or "always review my work," however explicit it was when
  originally given.

A standing preference of this kind may legitimately inform whether the
implementing Agent proactively *offers* or *asks about* running a local
review — but the offer/ask and the user's live answer to it are what
create authorization, never the standing preference by itself. Only a
request made in the current interaction, about the invocation under
consideration, counts.

## Silence and non-objection are not approval

Announcing an intended invocation and proceeding unless the user objects
is not a valid authorization flow:

```text
"I'll run a local code review now unless you object."
    ↓
no response / silence / user continues talking about something else
    ↓
invoke local-code-review anyway                                      ✗ prohibited
```

No response, silence, a delay before replying, continuing the
conversation without addressing the proposal, or any other form of
non-objection ever constitutes approval. Authorization requires an
affirmative instruction from the user requesting the review — see
"Scope of explicit approval" above for what that instruction must
contain.

## Orchestration mechanics never transfer the decision

`local-code-review` may be executed as an Agent/Sub-Agent according to
whatever orchestration model the implementing Agent uses — that is a
mechanical detail of how the invocation is technically carried out.
Invocation authority is unaffected by it: the end user is always the
one who chooses to run a specific review or re-review, never the
implementing Agent on its own initiative, regardless of whether the
Skill is invoked directly, through a Sub-Agent call, or through any
other delegation mechanism. An implementing Agent that has the
technical means to invoke this Skill as a delegated Agent/Sub-Agent
still must not exercise that capability without the same fresh,
explicit, per-run user approval required above — the ability to
delegate the call is not authorization to make the call. Delegation is
purely a mechanical execution detail: it must never create authorization
that does not otherwise exist, never broaden the scope the user actually
authorized (e.g. a request to review one file does not authorize
reviewing the whole repository), and never persist that authorization
beyond the one invocation it was obtained for.

## Caller/orchestrator responsibility boundary

Obtaining approval is entirely the responsibility of the caller, Team
Lead, runtime, or implementing workflow that invokes this Skill:

```text
caller/orchestrator
    ↓
determines whether review is desired
    ↓
asks user
    ↓
receives explicit approval for this run
    ↓
invokes local-code-review once
```

This Skill itself does not, and must not attempt to:

- ask the user for permission;
- verify that approval was obtained;
- decide whether another review iteration should happen;
- automatically schedule or self-trigger a re-review;
- continue a review/fix/review loop on its own.

This Skill has no mechanism to confirm approval occurred and does not
need one — that responsibility belongs entirely to the caller, never to
this Skill. This Skill only reviews the scope it was explicitly invoked
to review, once, per invocation; see
[`../SKILL.md`](../SKILL.md), "Statelessness and Orchestration Boundary."

## Structural limitation: this Skill cannot verify that approval occurred

Unlike `github-pr-review`'s self-review mutation boundary — which checks an
external, queryable fact (the authenticated GitHub identity, and its
controlling authority, against the PR author) and can therefore withhold a
formal `APPROVE` / `REQUEST_CHANGES` on its own — user approval for
`local-code-review` is a conversational fact with no external state this
Skill can query. This Skill has no mechanism to confirm, from inside a given
invocation, that a fresh, explicit, current-interaction approval actually
preceded it; see "Caller/orchestrator responsibility boundary" above.

This is an accepted structural limitation, not a reason to weaken or relax
this policy's requirements. It does not change any of the following:

- the caller/orchestrator remains entirely responsible for obtaining valid,
  fresh, per-invocation approval before invoking this Skill;
- this policy's approval contract (scope, non-persistence, the meaning-based
  authorization test) remains fully normative and unchanged;
- this Skill still must not ask for approval, verify it occurred, or treat
  its own invocation as evidence that approval existed.

Nothing here introduces an approval token, an approval file, hidden state, or
any other mechanism to persist or verify authorization — no such mechanism
exists in this Skill, and none is being added. The absence of a defensive,
self-verifiable guard is a known asymmetry with `github-pr-review`, not a gap
this policy attempts to close by other means.

## Why this exists

Without this invariant, a caller could treat `local-code-review` as an
implicit, automatic completion gate — running it after every
implementation step, or re-triggering it after every fix, without the
user ever having asked for that specific review. This policy exists so
that review remains a deliberate, user-authorized action rather than an
unrequested standing obligation.
